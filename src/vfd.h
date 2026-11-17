// Drawing of the ASR-10 vacuum fluorescent display for the SDL front end:
// 22 slanted 15-segment characters (14 segments + period) with an underline segment each,
// and the 29 annunciator legends in the upper half of the glass.
#pragma once
#include <SDL.h>
#include <cstdint>
#include "lcd.h"

class Panel;

class VfdRenderer {
public:
    bool init(SDL_Renderer *r);                 // builds the segment and legend textures
    // off-screen use (the plug-in editor): the textures scaled once for drawing at scale s, so
    // that the software renderer copies them without scaling
    bool prescale(float s);
    // x,y = top-left of the glass; s = scale (1 = WIDTH x HEIGHT logical px); glass = draw the
    // dark glass rectangle behind the digits
    void draw(const Panel &p, float x, float y, uint32_t ticks, float s = 1.0f, bool glass = true);
    static constexpr float WIDTH = 590, HEIGHT = 100;
    // the purple LCD instead of the VFD (same draw() call; the size of the screen differs)
    void set_lcd(bool on) { lcd_on = on; }
    bool lcd() const { return lcd_on; }
    float screen_width() const { return lcd_on ? LcdRenderer::WIDTH : WIDTH; }
    float screen_height() const { return lcd_on ? LcdRenderer::HEIGHT : HEIGHT; }
    ~VfdRenderer();

private:
    SDL_Renderer *R = nullptr;
    bool lcd_on = false;
    LcdRenderer lcd_r;
    static constexpr int NSEG = 16;            // 15 character segments + underline
    SDL_Texture *seg[NSEG] = {}, *seg_glow[NSEG] = {};
    SDL_Texture *leg[32] = {}, *leg_glow[32] = {};
    float ps = 0;                              // prescale(): the scale, and the scaled textures
    SDL_Texture *pseg[NSEG] = {}, *pseg_glow[NSEG] = {}, *pleg[32] = {}, *pleg_glow[32] = {};
    SDL_Texture *pghost = nullptr;             // all the segments of a cell in one (their unlit look)
    int nleg = 0;
    void cell(const Panel &p, int i, float x, float y, float s);
    bool blink_on = true;                  // phase of the blinking annunciators and characters
};
