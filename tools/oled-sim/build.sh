#!/bin/sh
# Build the OLED simulator from esp32.ino + the U8g2 C library.
#   ./build.sh path/to/esp32.ino path/to/U8g2/src/clib
set -e
INO=${1:-../../esp32.ino}
CLIB=${2:-$HOME/Arduino/libraries/U8g2/src/clib}
cd "$(dirname "$0")"

# drop fetchData(): it needs HTTP + ArduinoJson, and the simulator sets state directly
awk '/^void fetchData\(\) \{/{skip=1} !skip{print} skip&&/^\}/{skip=0}' "$INO" > sketch.cpp

if [ ! -f libu8g2.a ]; then
  mkdir -p obj
  for f in "$CLIB"/*.c; do gcc -O1 -c "$f" -I"$CLIB" -o "obj/$(basename "$f" .c).o" & done; wait
  ar rcs libu8g2.a obj/*.o
fi

g++ -std=c++17 -O1 -Ishim -I"$CLIB" sim.cpp libu8g2.a -o sim
echo "built ./sim"
