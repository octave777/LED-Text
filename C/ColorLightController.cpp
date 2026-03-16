#include "ColorLightController.hpp"
#include <iostream>
#include <cstring>
#include <cmath>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <chrono>

ColorLightController::ColorLightController(const std::string& iface, int w, int h, const std::string& order)
    : interface_name(iface), width(w), height(h), color_order(order), brightness(100), gamma(2.2), firmware_version(0), sock(-1) {
    update_gamma_table();
}

ColorLightController::~ColorLightController() {
    if (sock >= 0) {
        close(sock);
    }
}

void ColorLightController::update_gamma_table() {
    for (int i = 0; i < 256; ++i) {
        float f = 255.0f * std::pow(i / 255.0f, gamma);
        f = std::max(0.0f, std::min(255.0f, f));
        gamma_table[i] = static_cast<uint8_t>(std::round(f));
    }
}

std::vector<uint8_t> ColorLightController::convert_color_order(uint8_t r, uint8_t g, uint8_t b) {
    if (color_order == "BGR") return {b, g, r};
    if (color_order == "RGB") return {r, g, b};
    if (color_order == "GRB") return {g, r, b};
    if (color_order == "GBR") return {g, b, r};
    if (color_order == "RBG") return {r, b, g};
    if (color_order == "BRG") return {b, r, g};
    return {r, g, b};
}

bool ColorLightController::init_socket() {
    sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (sock < 0) {
        std::cerr << "소켓 생성 실패. sudo 권한이나 setcap cap_net_raw+ep가 필요합니다." << std::endl;
        return false;
    }

    struct ifreq ifr;
    std::memset(&ifr, 0, sizeof(ifr));
    std::strncpy(ifr.ifr_name, interface_name.c_str(), IFNAMSIZ - 1);

    if (ioctl(sock, SIOCGIFINDEX, &ifr) < 0) {
        std::cerr << "인터페이스 인덱스 획득 실패: " << interface_name << std::endl;
        return false;
    }

    std::memset(&device, 0, sizeof(device));
    device.sll_family = AF_PACKET;
    device.sll_ifindex = ifr.ifr_ifindex;
    device.sll_halen = ETH_ALEN;
    std::memcpy(device.sll_addr, dest_mac, ETH_ALEN);

    return true;
}

void ColorLightController::set_brightness(int b) {
    brightness = std::max(0, std::min(100, b));
}

void ColorLightController::set_gamma(float g) {
    gamma = g;
    update_gamma_table();
}

void ColorLightController::build_ether_header(uint8_t* buffer, uint16_t packet_type, uint8_t first_byte) {
    std::memcpy(buffer, dest_mac, 6);
    std::memcpy(buffer + 6, src_mac, 6);

    uint16_t eth_type;
    if (packet_type > 0xFF) {
        eth_type = packet_type;
    } else {
        eth_type = (packet_type << 8) | (first_byte & 0xFF);
    }
    eth_type = htons(eth_type);
    std::memcpy(buffer + 12, &eth_type, 2);
}

void ColorLightController::send_brightness() {
    if (sock < 0) return;

    uint8_t b_val = static_cast<uint8_t>(2.55 * brightness);
    uint8_t packet[14 + 64] = {0}; // 14 bytes eth header + 64 bytes payload

    build_ether_header(packet, CL_BRIG_PACKET_TYPE, b_val);

    uint8_t* payload = packet + 14;
    payload[0] = b_val;
    payload[1] = b_val;
    payload[2] = 0xFF;

    sendto(sock, packet, sizeof(packet), 0, (struct sockaddr*)&device, sizeof(device));
    if (firmware_version >= 13) {
        sendto(sock, packet, sizeof(packet), 0, (struct sockaddr*)&device, sizeof(device));
    }
}

void ColorLightController::send_pixel_data(const std::vector<uint8_t>& image_rgb) {
    if (sock < 0) return;

    for (int y = 0; y < height; ++y) {
        std::vector<uint8_t> row_pixels(width * 3, 0); // Background black
        
        // Copy image row if it exists
        // image_rgb format is tightly packed [r, g, b, r, g, b, ...] corresponding to width*height
        // In our C++ main, the generated image_rgb will be precisely width * height * 3
        if (y < height) {
            std::memcpy(row_pixels.data(), &image_rgb[y * width * 3], width * 3);
        }

        for (int x_offset = 0; x_offset < width; x_offset += CL_MAX_PIXL_PER_PACKET) {
            int chunk_size = std::min(CL_MAX_PIXL_PER_PACKET, width - x_offset);

            uint8_t row_msb = (y >> 8) & 0xFF;
            uint8_t row_lsb = y & 0xFF;
            uint8_t off_msb = (x_offset >> 8) & 0xFF;
            uint8_t off_lsb = x_offset & 0xFF;
            uint8_t cnt_msb = (chunk_size >> 8) & 0xFF;
            uint8_t cnt_lsb = chunk_size & 0xFF;

            std::vector<uint8_t> packet(14 + 7 + chunk_size * 3);
            build_ether_header(packet.data(), CL_PIXL_PACKET_TYPE, row_msb);

            uint8_t* payload = packet.data() + 14;
            payload[0] = row_lsb;
            payload[1] = off_msb;
            payload[2] = off_lsb;
            payload[3] = cnt_msb;
            payload[4] = cnt_lsb;
            payload[5] = 0x08;
            payload[6] = 0x00;

            uint8_t* pixel_dest = payload + 7;
            for (int i = 0; i < chunk_size; ++i) {
                int base_idx = (x_offset + i) * 3;
                uint8_t r = gamma_table[row_pixels[base_idx]];
                uint8_t g = gamma_table[row_pixels[base_idx + 1]];
                uint8_t b = gamma_table[row_pixels[base_idx + 2]];
                
                auto rgb_converted = convert_color_order(r, g, b);
                pixel_dest[i*3] = rgb_converted[0];
                pixel_dest[i*3 + 1] = rgb_converted[1];
                pixel_dest[i*3 + 2] = rgb_converted[2];
            }

            sendto(sock, packet.data(), packet.size(), 0, (struct sockaddr*)&device, sizeof(device));
            if (firmware_version >= 13) {
                sendto(sock, packet.data(), packet.size(), 0, (struct sockaddr*)&device, sizeof(device));
            }
        }
    }
}

void ColorLightController::send_sync() {
    if (sock < 0) return;

    std::vector<uint8_t> packet(14 + 1022, 0);
    build_ether_header(packet.data(), CL_SYNC_PACKET_TYPE, 0xFF);

    uint8_t* payload = packet.data() + 14;
    payload[0] = 0x00;
    payload[1] = 0xFF; payload[2] = 0xFF; payload[3] = 0xFF; payload[4] = 0xFF;
    payload[12] = 0x01;
    payload[17] = 0x01;
    payload[24] = 0xFF; payload[25] = 0xFF; payload[26] = 0xFD;
    
    uint8_t b_val = static_cast<uint8_t>(2.55 * brightness);
    payload[31] = b_val;

    sendto(sock, packet.data(), packet.size(), 0, (struct sockaddr*)&device, sizeof(device));
    if (firmware_version >= 13) {
        sendto(sock, packet.data(), packet.size(), 0, (struct sockaddr*)&device, sizeof(device));
    }
}

void ColorLightController::output_frame(const std::vector<uint8_t>& image_rgb) {
    send_brightness();
    send_pixel_data(image_rgb);
    send_sync();
}

void ColorLightController::detect_and_print_config() {
    if (sock < 0) return;
    
    std::cout << "--- Colorlight 카드 초기화 완료 (인터페이스: " << interface_name << ") ---\n";
    // Python detect logic involves sniff which is complex in pure C++ without pcap.
    // For this standalone headless implementation, we assume basic functional startup.
    // The C++ raw socket is strictly optimized for sending display payloads efficiently.
}
