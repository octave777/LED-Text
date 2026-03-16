#ifndef TEXT_RENDERER_HPP
#define TEXT_RENDERER_HPP

#include <string>
#include <vector>
#include <cstdint>

class TextRenderer {
public:
    struct Color {
        uint8_t r, g, b;
    };

    TextRenderer(int width, int height, const std::string& font_path);
    ~TextRenderer();

    bool is_loaded() const { return font_loaded; }
    std::vector<uint8_t> render_text(const std::string& text, int font_size, Color text_color, Color bg_color);

private:
    int panel_width;
    int panel_height;
    std::vector<unsigned char> font_buffer;
    bool font_loaded;
    void* font_info; // Opaque pointer to stbtt_fontinfo
};

#endif // TEXT_RENDERER_HPP
