#include <iostream>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <map>
#include <algorithm>
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
#include "ColorLightController.hpp"
#include "TextRenderer.hpp"

struct Config {
    std::string interface = "eth0";
    int width = 320;
    int height = 240;
    std::string color_order = "BGR";
    int font_size = 150;
    int initial_font_size = 50;
    std::string text_color = "white";
    std::string bg_color = "black";
    int brightness = 100;
    float gamma = 1.0f;
};

// 매우 간단한 JSON 파서 (정규식이나 외부 라이브러리 없이 구현)
Config load_config(const std::string& path) {
    Config cfg;
    std::ifstream file(path);
    if (!file.is_open()) return cfg;

    std::string line;
    while (std::getline(file, line)) {
        size_t colon = line.find(':');
        if (colon == std::string::npos) continue;

        std::string key = line.substr(0, colon);
        std::string val = line.substr(colon + 1);

        // 따옴표 및 공백 제거
        auto clean = [](std::string s) {
            s.erase(std::remove(s.begin(), s.end(), '\"'), s.end());
            s.erase(std::remove(s.begin(), s.end(), ','), s.end());
            s.erase(std::remove(s.begin(), s.end(), '{'), s.end());
            s.erase(std::remove(s.begin(), s.end(), '}'), s.end());
            size_t first = s.find_first_not_of(" \t\r\n");
            if (first == std::string::npos) return std::string("");
            size_t last = s.find_last_not_of(" \t\r\n");
            return s.substr(first, (last - first + 1));
        };

        key = clean(key);
        val = clean(val);

        if (key == "interface") cfg.interface = val;
        else if (key == "width") cfg.width = std::stoi(val);
        else if (key == "height") cfg.height = std::stoi(val);
        else if (key == "color_order") cfg.color_order = val;
        else if (key == "font_size") cfg.font_size = std::stoi(val);
        else if (key == "initial_font_size") cfg.initial_font_size = std::stoi(val);
        else if (key == "text_color") cfg.text_color = val;
        else if (key == "bg_color") cfg.bg_color = val;
        else if (key == "brightness") cfg.brightness = std::stoi(val);
        else if (key == "gamma") cfg.gamma = std::stof(val);
    }
    return cfg;
}

TextRenderer::Color parse_color(const std::string& name) {
    static std::map<std::string, TextRenderer::Color> colors = {
        {"white", {255, 255, 255}},
        {"black", {0, 0, 0}},
        {"red", {255, 0, 0}},
        {"green", {0, 255, 0}},
        {"blue", {0, 0, 255}}
    };
    if (colors.count(name)) return colors[name];
    return {255, 255, 255}; // 기본값 흰색
}

std::string get_input_interactively(const std::string& prompt) {
    std::cout << prompt << std::flush;
    std::string input_str = "";
    int fd = STDIN_FILENO;

    // 키패드 매핑 (NumLock Off 시 발생하는 ANSI 이스케이프 시퀀스)
    std::map<std::string, std::string> keypad_map = {
        {"\033[4~", "1"}, {"\033[F", "1"},    // 1 (End)
        {"\033[B", "2"},                    // 2 (Down)
        {"\033[6~", "3"},                   // 3 (PgDn)
        {"\033[D", "4"},                    // 4 (Left)
        {"\033[G", "5"}, {"\033[E", "5"},   // 5 (Center/Begin)
        {"\033[C", "6"},                    // 6 (Right)
        {"\033[1~", "7"}, {"\033[H", "7"},  // 7 (Home)
        {"\033[A", "8"},                    // 8 (Up)
        {"\033[5~", "9"},                   // 9 (PgUp)
        {"\033[2~", "0"},                   // 0 (Ins)
        {"\033[3~", "."},                   // . (Del)
        {"\033[Op", "0"}, {"\033[Oq", "1"}, {"\033[Or", "2"}, {"\033[Os", "3"},
        {"\033[Ot", "4"}, {"\033[Ou", "5"}, {"\033[Ov", "6"}, {"\033[Ow", "7"},
        {"\033[Ox", "8"}, {"\033[Oy", "9"}
    };

    struct termios oldt, newt;
    tcgetattr(fd, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(fd, TCSANOW, &newt);

    char ch;
    while (true) {
        if (read(fd, &ch, 1) <= 0) break;

        if (ch == 27) { // Escape sequence
            std::string seq = "\033";
            int flags = fcntl(fd, F_GETFL, 0);
            fcntl(fd, F_SETFL, flags | O_NONBLOCK);
            
            usleep(20000); // Wait for rest of sequence
            char next_ch;
            while (read(fd, &next_ch, 1) > 0) {
                seq += next_ch;
            }
            fcntl(fd, F_SETFL, flags);

            if (keypad_map.count(seq)) {
                ch = keypad_map[seq][0];
            } else {
                continue;
            }
        }

        if (ch == '\n' || ch == '\r') {
            std::cout << "\n";
            break;
        } else if (ch == 127 || ch == 8) { // Backspace
            if (!input_str.empty()) {
                input_str.pop_back();
                std::cout << "\b \b" << std::flush;
            }
        } else if (ch == 3) { // Ctrl+C
            tcsetattr(fd, TCSANOW, &oldt);
            exit(0);
        } else if (isprint(ch)) {
            input_str += ch;
            std::cout << ch << std::flush;
        }
    }

    tcsetattr(fd, TCSANOW, &oldt);
    return input_str;
}

int main() {
    Config cfg = load_config("LED_Config");

    std::cout << "--- ColorLight C++ v2 설정 ---" << std::endl;
    std::cout << "인터페이스: " << cfg.interface << std::endl;
    std::cout << "해상도: " << cfg.width << "x" << cfg.height << std::endl;
    std::cout << "색상 순서: " << cfg.color_order << std::endl;
    std::cout << "------------------------------" << std::endl;

    ColorLightController controller(cfg.interface, cfg.width, cfg.height, cfg.color_order);
    if (!controller.init_socket()) {
        return 1;
    }

    controller.set_brightness(cfg.brightness);
    controller.set_gamma(cfg.gamma);
    controller.detect_and_print_config();

    TextRenderer renderer(cfg.width, cfg.height, "font/GothicBold.ttf");
    if (!renderer.is_loaded()) {
        std::cerr << "렌더러 초기화 실패 (폰트 확인 필요)" << std::endl;
        return 1;
    }

    // 초기 이미지 전송 (50 크기 적용)
    std::string initial_text = "TLS Systems";
    auto img = renderer.render_text(initial_text, cfg.initial_font_size, parse_color(cfg.text_color), parse_color(cfg.bg_color));
    controller.output_frame(img);
    std::cout << "초기 이미지 전송 완료: '" << initial_text << "'" << std::endl;

    std::cout << "\n새로운 텍스트를 입력하고 Enter를 누르면 화면이 즉시 바뀝니다." << std::endl;
    std::cout << "종료하려면 Ctrl+C를 누르세요." << std::endl;

    std::string input_line;
    while (true) {
        input_line = get_input_interactively("\n[출력할 텍스트 입력]: ");
        if (input_line.empty()) continue;

        std::string display_text = input_line;
        if (display_text.length() > 3) {
            display_text = display_text.substr(display_text.length() - 3);
        }
        if (input_line.find('+') != std::string::npos) {
            display_text = " ";
        }

        auto new_img = renderer.render_text(display_text, cfg.font_size, parse_color(cfg.text_color), parse_color(cfg.bg_color));
        controller.output_frame(new_img);
        std::cout << ">> 전송 갱신됨: '" << display_text << "'" << std::endl;
    }

    return 0;
}
