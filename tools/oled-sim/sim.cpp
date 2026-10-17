// OLED simulator: runs the real esp32.ino drawing code and records every
// frame the sketch sends to the display.
//
//   sim <mode> <out.bin> <frames> [title artist pos_ms dur_ms lyric next]
//   mode: boot | play | lyrics | idle
#include "sketch.cpp"

unsigned long sim_ms = 0;
static FILE* out = nullptr;
static bool capture = false;

void sim_frame(const uint8_t* buf) {
  sim_ms += 25;  // ~1 KB over 400 kHz I2C
  if (capture && out) fwrite(buf, 1, 1024, out);
}

int main(int argc, char** argv) {
  if (argc < 4) return 1;
  String mode = argv[1];
  out = fopen(argv[2], "wb");
  int frames = atoi(argv[3]);
  srand(7);

  u8g2.begin();

  if (mode == "boot") {
    capture = true;
    setup();
    return 0;
  }

  setup();  // run the boot sequence uncaptured so state matches the device
  if (argc >= 10) {
    currTitle = argv[4];
    currArtist = argv[5];
    serverPositionMs = atol(argv[6]);
    durationMs = atol(argv[7]);
    lyricCurr = argv[8];
    lyricNext = argv[9];
  }
  playing = (mode != "idle");
  if (mode == "idle") currTitle = "";
  screenMode = (mode == "lyrics") ? 1 : 0;
  fetchedAt = millis();
  titleX = 0;  // start with the title on screen instead of scrolling in

  capture = true;
  for (int i = 0; i < frames; i++) loop();
  return 0;
}
