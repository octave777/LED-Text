#ifndef COLORLIGHT_CONTROLLER_HPP
#define COLORLIGHT_CONTROLLER_HPP

#include <string>
#include <vector>
#include <cstdint>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>

class ColorLightController {
private:
    std::string interface_name;
    int width;
    int height;
    std::string color_order;
    int brightness;
    float gamma;
    int firmware_version;

    uint8_t gamma_table[256];
    int sock;
    struct sockaddr_ll device;

    void update_gamma_table();
    std::vector<uint8_t> convert_color_order(uint8_t r, uint8_t g, uint8_t b);
    void build_ether_header(uint8_t* buffer, uint16_t packet_type, uint8_t first_byte);

    static constexpr uint16_t CL_SYNC_PACKET_TYPE = 0x01;
    static constexpr uint16_t CL_BRIG_PACKET_TYPE = 0x0A;
    static constexpr uint16_t CL_PIXL_PACKET_TYPE = 0x55;
    static constexpr int CL_MAX_PIXL_PER_PACKET = 400;

    uint8_t dest_mac[6] = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    uint8_t src_mac[6] = {0x22, 0x22, 0x33, 0x44, 0x55, 0x66};

public:
    ColorLightController(const std::string& iface, int w, int h, const std::string& order);
    ~ColorLightController();

    bool init_socket();
    void set_brightness(int b);
    void set_gamma(float g);
    void set_firmware_version(int fw) { firmware_version = fw; }

    void send_brightness();
    void send_pixel_data(const std::vector<uint8_t>& image_rgb);
    void send_sync();
    void output_frame(const std::vector<uint8_t>& image_rgb);
    void detect_and_print_config();
};

#endif // COLORLIGHT_CONTROLLER_HPP
