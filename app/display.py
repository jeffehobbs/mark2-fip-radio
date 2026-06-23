#!/usr/bin/env python3
"""Lightweight FIP now-playing renderer -> Linux framebuffer (/dev/fb0).

No browser / X / Wayland. Polls the local FIP backend (which queries the
Radio France API), draws an 800x480 now-playing screen with PIL, and writes
it straight to the framebuffer. Run with --shot <png> to dump one frame.
"""
import sys, os, time, json, io, urllib.request

from PIL import Image, ImageDraw, ImageFont

API = "http://localhost:8080/api/now"
FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"
PINK = (230, 0, 90)
BG = (10, 10, 12)


def fb_geometry():
    def rd(p, d=None):
        try:
            return open(p).read().strip()
        except Exception:
            return d
    w, h = (int(x) for x in rd("/sys/class/graphics/fb0/virtual_size", "800,480").split(","))
    bpp = int(rd("/sys/class/graphics/fb0/bits_per_pixel", "32"))
    stride = int(rd("/sys/class/graphics/fb0/stride", str(w * (bpp // 8))))
    return w, h, bpp, stride


def font(sz, bold=True):
    try:
        return ImageFont.truetype(FONT if bold else FONT_R, sz)
    except Exception:
        return ImageFont.load_default()


def wrap(draw, text, fnt, max_w, max_lines=3):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = wd
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1], font=fnt) > max_w:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=fnt) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


_cover_cache = {}


def get_cover(url, size):
    if not url:
        return None
    key = (url, size)
    if key in _cover_cache:
        return _cover_cache[key]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=8).read()
        im = Image.open(io.BytesIO(data)).convert("RGB").resize((size, size))
        _cover_cache.clear()
        _cover_cache[key] = im
        return im
    except Exception:
        return None


def draw_mic(d, cx, cy, color):
    """A simple microphone glyph, centered on (cx, cy). Drawn with primitives
    so it doesn't depend on any installed font/emoji coverage."""
    d.rounded_rectangle([cx - 38, cy - 95, cx + 38, cy + 15], radius=38, fill=color)  # capsule
    d.arc([cx - 62, cy - 40, cx + 62, cy + 66], start=15, end=165, fill=color, width=10)  # cradle
    d.line([(cx, cy + 66), (cx, cy + 100)], fill=color, width=10)                     # stem
    d.line([(cx - 38, cy + 102), (cx + 38, cy + 102)], fill=color, width=10)          # base


def render(w, h, data):
    img = Image.new("RGB", (w, h), BG)
    cover = data.get("cover") or ""
    is_art = cover.startswith("http")              # songs carry a URL; talk segments carry a bare id
    # blurred cover backdrop
    cov = get_cover(cover, 360) if is_art else None
    if cov:
        try:
            from PIL import ImageFilter, ImageEnhance
            bg = cov.resize((w, w)).crop((0, (w - h) // 2, w, (w - h) // 2 + h))
            bg = bg.filter(ImageFilter.GaussianBlur(40))
            bg = ImageEnhance.Brightness(bg).enhance(0.35)
            img.paste(bg, (0, 0))
        except Exception:
            pass
    d = ImageDraw.Draw(img)
    # cover art (left)
    art_x, art_y, art = 40, 80, 320
    c = get_cover(cover, art) if is_art else None
    if c:
        img.paste(c, (art_x, art_y))
    else:
        d.rounded_rectangle([art_x, art_y, art_x + art, art_y + art], 16, fill=(34, 34, 38))
        if not is_art:                             # announcement/show: no album art -> mic glyph
            draw_mic(d, art_x + art // 2, art_y + art // 2, (210, 210, 215))
    # right column
    rx = art_x + art + 36
    rw = w - rx - 36
    playing = data.get("playing", True)
    # FIP badge
    badge = font(26)
    bw = d.textlength("FIP", font=badge) + 28
    d.rounded_rectangle([rx, 96, rx + bw, 96 + 44], 8, fill=PINK)
    d.text((rx + 14, 102), "FIP", font=badge, fill=(255, 255, 255))
    if not playing:
        # stopped (audio off): show a play ▶ affordance, not pause bars.
        # Drawn as a polygon so it doesn't depend on font glyph coverage.
        ix, iy, isz = rx + bw + 16, 100, 26
        d.polygon([(ix, iy), (ix, iy + isz), (ix + isz * 0.88, iy + isz / 2)],
                  fill=(180, 180, 180))
    y = 165
    title = data.get("title") or "FIP"
    tf = font(40)
    for ln in wrap(d, title, tf, rw, 3):
        d.text((rx, y), ln, font=tf, fill=(255, 255, 255))
        y += 50
    y += 6
    if data.get("artist"):
        af = font(30)
        d.text((rx, y), wrap(d, data["artist"], af, rw, 1)[0], font=af, fill=PINK)
        y += 44
    sub = data.get("album") or ""
    if data.get("year"):
        sub = (sub + "  ·  " + str(data["year"])) if sub else str(data["year"])
    if sub:
        sf = font(20, bold=False)
        d.text((rx, y), wrap(d, sub, sf, rw, 1)[0], font=sf, fill=(180, 180, 180))
    # progress bar
    s, e = data.get("start", 0), data.get("end", 0)
    if s and e and e > s:
        p = max(0.0, min(1.0, (time.time() - s) / (e - s)))
        d.rectangle([0, h - 6, int(w * p), h], fill=PINK)
    return img


def to_fb_bytes(img, bpp):
    if bpp == 32:
        return img.convert("RGB").tobytes("raw", "BGRX")
    elif bpp == 16:
        import numpy as np
        a = np.asarray(img.convert("RGB"), dtype=np.uint16)
        r, g, b = a[..., 0] >> 3, a[..., 1] >> 2, a[..., 2] >> 3
        return ((r << 11) | (g << 5) | b).astype("<u2").tobytes()
    return img.convert("RGB").tobytes("raw", "BGRX")


def write_fb(img, w, h, bpp, stride):
    raw = to_fb_bytes(img, bpp)
    bpl = w * (bpp // 8)
    with open("/dev/fb0", "wb") as fb:
        if stride == bpl:
            fb.write(raw)
        else:                       # honor padded stride
            for row in range(h):
                fb.seek(row * stride)
                fb.write(raw[row * bpl:(row + 1) * bpl])


def fetch():
    try:
        return json.loads(urllib.request.urlopen(API, timeout=6).read())
    except Exception:
        return {"title": "FIP", "artist": "", "album": "", "year": "",
                "cover": "", "start": 0, "end": 0, "playing": False}


def main():
    w, h, bpp, stride = fb_geometry()
    if len(sys.argv) > 2 and sys.argv[1] == "--shot":
        render(w, h, fetch()).save(sys.argv[2])
        return
    last = 0
    data = fetch()
    while True:
        if time.time() - last > 8:      # refresh metadata every 8s
            data = fetch()
            last = time.time()
        try:
            write_fb(render(w, h, data), w, h, bpp, stride)
        except Exception as e:
            sys.stderr.write(f"render error: {e}\n")
        time.sleep(1)                   # progress bar ticks each second


if __name__ == "__main__":
    main()
