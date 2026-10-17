"""Turn raw SH1106 frame dumps from sim into OLED-looking PNG / GIF.

    render.py frames.bin out.png [frame_index]
    render.py frames.bin out.gif start:stop:step [ms_per_frame]
"""
import sys

from PIL import Image, ImageDraw, ImageFilter

W, H = 128, 64
PX, GAP = 5, 1           # each OLED pixel drawn as a 4x4 dot with a 1px gap
PAD = 28                 # black glass around the active area
ON = (214, 236, 255)     # white OLED with a slight cool tint
OFF = (14, 16, 20)
GLASS = (6, 7, 9)
BEZEL = (28, 30, 34)


def frames(path):
    data = open(path, "rb").read()
    return [data[i:i + 1024] for i in range(0, len(data) - 1023, 1024)]


def to_image(buf):
    # full-buffer layout: 8 pages x 128 columns, each byte = 8 vertical pixels, LSB on top
    aw, ah = W * PX, H * PX
    glass = Image.new("RGB", (aw + 2 * PAD, ah + 2 * PAD), GLASS)
    dots = Image.new("RGB", glass.size, GLASS)
    d = ImageDraw.Draw(dots)
    for page in range(8):
        for x in range(W):
            byte = buf[page * W + x]
            for bit in range(8):
                y = page * 8 + bit
                c = ON if byte >> bit & 1 else OFF
                x0, y0 = PAD + x * PX, PAD + y * PX
                d.rectangle([x0, y0, x0 + PX - GAP - 1, y0 + PX - GAP - 1], fill=c)
    glow = dots.filter(ImageFilter.GaussianBlur(3))
    lit = Image.blend(glow, dots, 0.75)
    out = Image.new("RGB", (lit.width + 16, lit.height + 16), BEZEL)
    out.paste(lit, (8, 8))
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    fr = frames(src)
    if dst.endswith(".gif"):
        a, b, s = (int(v) for v in sys.argv[3].split(":"))
        ms = int(sys.argv[4]) if len(sys.argv) > 4 else 60
        imgs = [to_image(f).quantize(colors=64) for f in fr[a:b:s]]
        imgs[0].save(dst, save_all=True, append_images=imgs[1:], duration=ms, loop=0, optimize=True)
    else:
        i = int(sys.argv[3]) if len(sys.argv) > 3 else -1
        to_image(fr[i]).save(dst, optimize=True)
    print(f"{dst}: {len(fr)} frames available")


if __name__ == "__main__":
    main()
