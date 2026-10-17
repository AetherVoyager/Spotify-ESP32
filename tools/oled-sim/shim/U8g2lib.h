// Host-side stand-in for the Arduino U8g2 class: same method names the
// sketch uses, backed by the real U8g2 C library drawing into RAM.
#pragma once
#include "Arduino.h"
extern "C" {
#include "u8g2.h"
}

void sim_frame(const uint8_t* buf);  // called on every sendBuffer()

class U8G2_SH1106_128X64_NONAME_F_HW_I2C {
 public:
  u8g2_t u8g2;
  U8G2_SH1106_128X64_NONAME_F_HW_I2C(const u8g2_cb_t* rot, uint8_t) {
    u8g2_Setup_sh1106_128x64_noname_f(&u8g2, rot, u8x8_byte_empty, u8x8_dummy_cb);
  }
  bool begin() { u8g2_InitDisplay(&u8g2); clearBuffer(); return true; }
  void clearBuffer() { u8g2_ClearBuffer(&u8g2); }
  void sendBuffer() { sim_frame(u8g2_GetBufferPtr(&u8g2)); }
  void setFont(const uint8_t* f) { u8g2_SetFont(&u8g2, f); }
  void setDrawColor(uint8_t c) { u8g2_SetDrawColor(&u8g2, c); }
  u8g2_uint_t getUTF8Width(const char* s) { return u8g2_GetUTF8Width(&u8g2, s); }
  u8g2_uint_t drawStr(int x, int y, const char* s) { return u8g2_DrawStr(&u8g2, x, y, s); }
  void drawXBMP(int x, int y, int w, int h, const uint8_t* b) { u8g2_DrawXBMP(&u8g2, x, y, w, h, b); }
  void drawBox(int x, int y, int w, int h) { u8g2_DrawBox(&u8g2, x, y, w, h); }
  void drawFrame(int x, int y, int w, int h) { u8g2_DrawFrame(&u8g2, x, y, w, h); }
  void drawHLine(int x, int y, int w) { u8g2_DrawHLine(&u8g2, x, y, w); }
  void drawVLine(int x, int y, int h) { u8g2_DrawVLine(&u8g2, x, y, h); }
  void drawPixel(int x, int y) { u8g2_DrawPixel(&u8g2, x, y); }
  void drawLine(int x1, int y1, int x2, int y2) { u8g2_DrawLine(&u8g2, x1, y1, x2, y2); }
  void drawDisc(int x, int y, int r) { u8g2_DrawDisc(&u8g2, x, y, r, U8G2_DRAW_ALL); }
  void drawFilledEllipse(int x, int y, int rx, int ry) { u8g2_DrawFilledEllipse(&u8g2, x, y, rx, ry, U8G2_DRAW_ALL); }
  void setClipWindow(int x0, int y0, int x1, int y1) { u8g2_SetClipWindow(&u8g2, x0, y0, x1, y1); }
  void setMaxClipWindow() { u8g2_SetMaxClipWindow(&u8g2); }
};
