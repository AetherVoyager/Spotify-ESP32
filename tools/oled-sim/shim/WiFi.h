#pragma once
#include "Arduino.h"

#define WL_CONNECTED 3

struct IPStub { String toString() { return "192.168.1.42"; } };
struct WiFiStub {
  void begin(const char*, const char*) {}
  int status() { return WL_CONNECTED; }
  IPStub localIP() { return {}; }
};
inline WiFiStub WiFi;

// fetchData() is stripped from the sketch; the simulator sets state directly
inline void fetchData() {}
