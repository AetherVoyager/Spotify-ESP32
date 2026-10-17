// Minimal Arduino API so esp32.ino compiles on a PC.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

using std::max;
using std::min;

class String {
 public:
  std::string s;
  String() {}
  String(const char* c) : s(c ? c : "") {}
  String(const std::string& x) : s(x) {}
  const char* c_str() const { return s.c_str(); }
  unsigned length() const { return s.size(); }
  bool isEmpty() const { return s.empty(); }
  void remove(unsigned i) { if (i < s.size()) s.erase(i); }
  String operator+(const String& o) const { return String(s + o.s); }
  String operator+(const char* o) const { return String(s + o); }
  bool operator==(const String& o) const { return s == o.s; }
  bool operator!=(const String& o) const { return s != o.s; }
};
inline String operator+(const char* a, const String& b) { return String(std::string(a) + b.s); }

extern unsigned long sim_ms;
inline unsigned long millis() { return sim_ms; }
inline void delay(unsigned long ms) { sim_ms += ms; }
inline long random(long hi) { return hi > 0 ? std::rand() % hi : 0; }
inline long random(long lo, long hi) { return hi > lo ? lo + std::rand() % (hi - lo) : lo; }
inline void randomSeed(unsigned long s) { std::srand(s); }
inline int analogRead(int) { return 0; }
inline long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }
template <class T, class L, class H>
T constrain(T x, L lo, H hi) { return x < lo ? lo : (x > hi ? hi : x); }

struct SerialStub {
  void begin(long) {}
  template <class T> void print(const T&) {}
  template <class T> void println(const T&) {}
  void println() {}
};
inline SerialStub Serial;
