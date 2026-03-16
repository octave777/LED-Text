#define STB_TRUETYPE_IMPLEMENTATION
#include "stb_truetype.h"
#include "TextRenderer.hpp"
#include <fstream>
#include <iostream>
#include <algorithm>

TextRenderer::TextRenderer(int width, int height, const std::string& font_path)
    : panel_width(width), panel_height(height), font_loaded(false) {
    
    std::ifstream file(font_path, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        std::cerr << "폰트 파일을 열 수 없습니다: " << font_path << std::endl;
        return;
    }

    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    font_buffer.resize(size);
    if (file.read((char*)font_buffer.data(), size)) {
        font_info = malloc(sizeof(stbtt_fontinfo));
        if (stbtt_InitFont((stbtt_fontinfo*)font_info, font_buffer.data(), 0)) {
            font_loaded = true;
        } else {
            std::cerr << "폰트 초기화 실패" << std::endl;
            free(font_info);
            font_info = nullptr;
        }
    }
}

TextRenderer::~TextRenderer() {
    if (font_info) {
        free(font_info);
    }
}

std::vector<uint8_t> TextRenderer::render_text(const std::string& text, int font_size, Color text_color, Color bg_color) {
    // 최종 RGB 버퍼 초기화 (배경색으로)
    std::vector<uint8_t> rgb_buffer(panel_width * panel_height * 3);
    for (int i = 0; i < panel_width * panel_height; ++i) {
        rgb_buffer[i * 3 + 0] = bg_color.r;
        rgb_buffer[i * 3 + 1] = bg_color.g;
        rgb_buffer[i * 3 + 2] = bg_color.b;
    }

    if (!font_loaded || text.empty()) return rgb_buffer;

    stbtt_fontinfo* info = (stbtt_fontinfo*)font_info;
    float scale = stbtt_ScaleForPixelHeight(info, (float)font_size);

    int ascent, descent, lineGap;
    stbtt_GetFontVMetrics(info, &ascent, &descent, &lineGap);

    int text_width = 0;
    // 전체 텍스트 상하 경계 및 너비 계산
    int min_y = 9999, max_y = -9999;
    for (int i = 0; i < text.length(); ++i) {
        int char_x0, char_y0, char_x1, char_y1;
        stbtt_GetCodepointBitmapBox(info, text[i], scale, scale, &char_x0, &char_y0, &char_x1, &char_y1);
        if (char_y0 < min_y) min_y = char_y0;
        if (char_y1 > max_y) max_y = char_y1;

        int advance, lsb;
        stbtt_GetCodepointHMetrics(info, text[i], &advance, &lsb);
        text_width += advance * scale;
        if (i < text.length() - 1) {
            text_width += scale * stbtt_GetCodepointKernAdvance(info, text[i], text[i + 1]);
        }
    }
    int text_height = max_y - min_y;

    // 중앙 정렬을 위한 시작 위치 계산
    int start_x = (panel_width - text_width) / 2;
    int baseline = (panel_height - text_height) / 2 - min_y;

    int current_x = start_x;
    for (int i = 0; i < text.length(); ++i) {
        int char_x0, char_y0, char_x1, char_y1;
        stbtt_GetCodepointBitmapBox(info, text[i], scale, scale, &char_x0, &char_y0, &char_x1, &char_y1);

        int out_y = baseline + char_y0;
        int out_x = current_x + char_x0;

        int byte_width = char_x1 - char_x0;
        int byte_height = char_y1 - char_y0;

        if (byte_width > 0 && byte_height > 0) {
            std::vector<uint8_t> bitmap(byte_width * byte_height);
            stbtt_MakeCodepointBitmap(info, bitmap.data(), byte_width, byte_height, byte_width, scale, scale, text[i]);

            for (int y = 0; y < byte_height; ++y) {
                for (int x = 0; x < byte_width; ++x) {
                    int px = out_x + x;
                    int py = out_y + y;
                    if (px >= 0 && px < panel_width && py >= 0 && py < panel_height) {
                        float alpha = bitmap[y * byte_width + x] / 255.0f;
                        int idx = (py * panel_width + px) * 3;
                        rgb_buffer[idx + 0] = (uint8_t)(rgb_buffer[idx + 0] * (1.0f - alpha) + text_color.r * alpha);
                        rgb_buffer[idx + 1] = (uint8_t)(rgb_buffer[idx + 1] * (1.0f - alpha) + text_color.g * alpha);
                        rgb_buffer[idx + 2] = (uint8_t)(rgb_buffer[idx + 2] * (1.0f - alpha) + text_color.b * alpha);
                    }
                }
            }
        }

        int advance, lsb;
        stbtt_GetCodepointHMetrics(info, text[i], &advance, &lsb);
        current_x += advance * scale;
        if (i < text.length() - 1) {
            current_x += scale * stbtt_GetCodepointKernAdvance(info, text[i], text[i + 1]);
        }
    }

    return rgb_buffer;
}
