"""
village_art.py - draws 2D cartoon village scenes with Pillow (no AI images).
12 fixed faces (6 male, 6 female). Dress colour/pattern, names and emotions change per video.
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H, S = 1280, 720, 2          # final size, supersample factor
OUT = (55, 38, 30)              # outline colour

BACKGROUNDS = ["village_street", "shop", "market", "field",
               "house_inside", "night_village", "haunted_tree", "river"]
EMOTIONS = ["neutral", "happy", "sad", "angry", "surprised", "scared"]
PATTERNS = ["plain", "stripes", "checks", "dots", "border"]
PALETTE = [(200, 50, 50), (40, 110, 200), (30, 150, 80), (230, 160, 30), (140, 60, 160),
           (230, 110, 150), (20, 150, 160), (230, 100, 40), (120, 85, 55), (90, 100, 125),
           (170, 30, 90), (60, 60, 140)]
LOWERS = [(238, 236, 228), (225, 215, 190), (70, 70, 85), (120, 100, 80)]

# 6 male + 6 female fixed faces
FACES = {
    "m1": dict(gender="m", age="child",  skin=(214, 160, 118), hair="short",    hair_c=(30, 22, 18),    extra=[]),
    "m2": dict(gender="m", age="young",  skin=(196, 140, 98),  hair="short",    hair_c=(25, 20, 18),    extra=[]),
    "m3": dict(gender="m", age="young",  skin=(222, 170, 128), hair="side",     hair_c=(28, 22, 20),    extra=["mustache"]),
    "m4": dict(gender="m", age="middle", skin=(178, 122, 84),  hair="bald",     hair_c=(60, 50, 45),    extra=["mustache", "belly"]),
    "m5": dict(gender="m", age="old",    skin=(190, 135, 95),  hair="pagri",    hair_c=(235, 235, 235), extra=["whitebeard", "mustache", "wrinkles"]),
    "m6": dict(gender="m", age="middle", skin=(160, 106, 70),  hair="short",    hair_c=(30, 24, 20),    extra=["mustache", "glasses"]),
    "f1": dict(gender="f", age="child",  skin=(218, 166, 124), hair="pigtails", hair_c=(30, 22, 18),    extra=["blush"]),
    "f2": dict(gender="f", age="young",  skin=(204, 148, 106), hair="braid",    hair_c=(25, 20, 18),    extra=["blush"]),
    "f3": dict(gender="f", age="young",  skin=(226, 176, 134), hair="bun",      hair_c=(35, 25, 22),    extra=["blush", "bindi"]),
    "f4": dict(gender="f", age="middle", skin=(182, 126, 88),  hair="bun",      hair_c=(40, 30, 28),    extra=["bindi"]),
    "f5": dict(gender="f", age="old",    skin=(192, 138, 98),  hair="bun",      hair_c=(225, 225, 225), extra=["wrinkles"]),
    "f6": dict(gender="f", age="middle", skin=(166, 112, 76),  hair="parted",   hair_c=(28, 22, 20),    extra=["bindi", "round"]),
}
AGE_SCALE = {"child": 0.68, "young": 0.97, "middle": 1.0, "old": 0.94}


def B(box):
    return tuple(int(v * S) for v in box)


def P(pts):
    return [(x * S, y * S) for x, y in pts]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ characters
def patterned(size, c1, c2, pat):
    layer = Image.new("RGBA", size, c1 + (255,))
    d = ImageDraw.Draw(layer)
    w, h = size
    step = 22 * S
    if pat == "stripes":
        for x in range(0, w, step * 2):
            d.rectangle([x, 0, x + step, h], fill=c2)
    elif pat == "checks":
        for y in range(0, h, step):
            for x in range(0, w, step):
                if ((x // step) + (y // step)) % 2 == 0:
                    d.rectangle([x, y, x + step - 1, y + step - 1], fill=c2)
    elif pat == "dots":
        for row, y in enumerate(range(step // 2, h, step)):
            for x in range(step // 2 + (row % 2) * (step // 2), w, step):
                d.ellipse([x - 4 * S, y - 4 * S, x + 4 * S, y + 4 * S], fill=c2)
    elif pat == "border":
        for y in range(0, h, 70 * S):
            d.rectangle([0, y, w, y + 10 * S], fill=c2)
    return layer


def paint(img, fn, fill, outline=True):
    mask = Image.new("L", img.size, 0)
    fn(ImageDraw.Draw(mask))
    if isinstance(fill[0], tuple):
        layer = patterned(img.size, fill[0], fill[1], fill[2])
    else:
        layer = Image.new("RGBA", img.size, tuple(fill) + (255,))
    if outline:
        edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
        img.paste(Image.new("RGBA", img.size, OUT + (255,)), (0, 0), edge)
    img.paste(layer, (0, 0), mask)


def E(x0, y0, x1, y1):
    return lambda m: m.ellipse(B((x0, y0, x1, y1)), fill=255)


def RR(x0, y0, x1, y1, r):
    return lambda m: m.rounded_rectangle(B((x0, y0, x1, y1)), radius=r * S, fill=255)


def PO(pts):
    return lambda m: m.polygon(P(pts), fill=255)


def draw_character(face_id, dress, emotion):
    f = FACES[face_id]
    cw, ch, cx = 360, 640, 180
    img = Image.new("RGBA", (cw * S, ch * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    skin, hair, g, ex = f["skin"], f["hair_c"], f["gender"], f["extra"]
    c1, c2, pat, lower = dress["c1"], dress["c2"], dress["pat"], dress["lower"]
    main = (c1, c2, pat)
    shoe = (40, 30, 28)
    tw = 78 if "belly" in ex else 62
    fw = 58 if ("round" in ex or "belly" in ex) else 52
    hs = f["hair"]

    # --- back hair
    if hs == "braid":
        paint(img, E(cx + 36, 185, cx + 82, 372), hair)
    if hs == "pigtails":
        paint(img, E(cx - fw - 40, 150, cx - fw + 8, 200), hair)
        paint(img, E(cx + fw - 8, 150, cx + fw + 40, 200), hair)
    if hs == "bun":
        paint(img, E(cx - 26, 90, cx + 26, 142), hair)

    # --- body
    if g == "m":
        paint(img, RR(cx - 40, 460, cx - 4, 612, 10), lower)
        paint(img, RR(cx + 4, 460, cx + 40, 612, 10), lower)
        paint(img, E(cx - 52, 600, cx - 2, 628), shoe)
        paint(img, E(cx + 2, 600, cx + 52, 628), shoe)
        paint(img, RR(cx - tw, 262, cx + tw, 490, 30), main)
        paint(img, PO([(cx - tw + 8, 272), (cx - tw - 26, 288), (cx - tw - 30, 428), (cx - tw + 4, 428)]), main)
        paint(img, PO([(cx + tw - 8, 272), (cx + tw + 26, 288), (cx + tw + 30, 428), (cx + tw - 4, 428)]), main)
        paint(img, E(cx - tw - 46, 418, cx - tw - 12, 452), skin)
        paint(img, E(cx + tw + 12, 418, cx + tw + 46, 452), skin)
    else:
        paint(img, E(cx - 50, 600, cx - 4, 628), shoe)
        paint(img, E(cx + 4, 600, cx + 50, 628), shoe)
        paint(img, PO([(cx - 52, 330), (cx + 52, 330), (cx + 92, 614), (cx - 92, 614)]), main)
        paint(img, PO([(cx - 50, 274), (cx - 78, 290), (cx - 90, 422), (cx - 66, 426)]), skin)
        paint(img, PO([(cx + 50, 274), (cx + 78, 290), (cx + 90, 422), (cx + 66, 426)]), skin)
        paint(img, E(cx - 98, 418, cx - 62, 452), skin)
        paint(img, E(cx + 62, 418, cx + 98, 452), skin)
        paint(img, RR(cx - 50, 262, cx + 50, 346, 22), c2)
        paint(img, PO([(cx - 82, 284), (cx - 52, 270), (cx - 48, 322), (cx - 80, 330)]), c2)
        paint(img, PO([(cx + 82, 284), (cx + 52, 270), (cx + 48, 322), (cx + 80, 330)]), c2)
        paint(img, PO([(cx - 46, 268), (cx - 14, 268), (cx + 62, 430), (cx + 30, 444)]), (c1, c2, "border" if pat == "plain" else pat))

    # --- neck, ears, face
    paint(img, RR(cx - 15, 228, cx + 15, 276, 6), skin)
    paint(img, E(cx - fw - 8, 178, cx - fw + 8, 214), skin)
    paint(img, E(cx + fw - 8, 178, cx + fw + 8, 214), skin)
    paint(img, E(cx - fw, 128, cx + fw, 254), skin)

    # --- beard (before mouth)
    if "whitebeard" in ex:
        paint(img, PO([(cx - 50, 222), (cx - 44, 264), (cx - 24, 288), (cx, 296), (cx + 24, 288), (cx + 44, 264),
                       (cx + 50, 222), (cx + 34, 252), (cx, 262), (cx - 34, 252)]), (235, 235, 235))

    # --- front hair / turban
    def cap(m):
        m.pieslice(B((cx - fw - 4, 118, cx + fw + 4, 262)), 180, 360, fill=255)
        m.ellipse(B((cx - fw + 6, 150, cx + fw - 6, 272)), fill=0)

    if hs in ("short", "side", "bun", "pigtails", "braid", "parted"):
        paint(img, cap, hair)
    if hs == "side":
        paint(img, PO([(cx - 10, 124), (cx + fw + 2, 150), (cx + fw - 6, 172), (cx + 10, 148)]), hair)
    if hs == "parted":
        d.line(P([(cx, 120), (cx, 152)]), fill=OUT, width=3 * S)
    if hs == "bald":
        paint(img, E(cx - fw - 6, 160, cx - fw + 12, 204), hair)
        paint(img, E(cx + fw - 12, 160, cx + fw + 6, 204), hair)
    if hs == "pagri":
        paint(img, E(cx - fw - 12, 92, cx + fw + 12, 172), (c2, c1, "stripes"))
        paint(img, PO([(cx + fw, 120), (cx + fw + 30, 150), (cx + fw + 22, 210), (cx + fw + 4, 150)]), c2)

    # --- eyes + brows
    for sx in (-20, 20):
        x, y = cx + sx, 192
        if emotion == "happy":
            d.arc(B((x - 11, 184, x + 11, 206)), 200, 340, fill=OUT, width=3 * S)
        else:
            ry = 13 if emotion in ("surprised", "scared") else 9
            d.ellipse(B((x - 11, y - ry, x + 11, y + ry)), fill=(255, 255, 255), outline=OUT, width=2 * S)
            off = 2 if emotion == "angry" else 0
            d.ellipse(B((x - 5 + off, y - 5, x + 5 + off, y + 5)), fill=(30, 20, 15))
            d.ellipse(B((x - 2 + off, y - 4, x + 1 + off, y - 1)), fill=(255, 255, 255))
    by = {"neutral": (172, 172), "happy": (168, 168), "sad": (176, 166),
          "angry": (166, 176), "surprised": (158, 158), "scared": (160, 164)}[emotion]
    bc = hair if hair[0] < 200 else (150, 150, 150)
    for side in (-1, 1):
        xo, xi = cx + side * 32, cx + side * 8
        d.line(P([(xo, by[0]), (xi, by[1])]), fill=bc, width=4 * S)

    # --- nose, mouth
    sk_d = lerp(skin, (60, 30, 20), 0.35)
    d.arc(B((cx - 8, 204, cx + 8, 220)), 20, 160, fill=sk_d, width=3 * S)
    if emotion == "happy":
        d.chord(B((cx - 20, 222, cx + 20, 250)), 0, 180, fill=(170, 45, 45), outline=OUT, width=2 * S)
    elif emotion == "sad":
        d.arc(B((cx - 14, 238, cx + 14, 258)), 200, 340, fill=OUT, width=3 * S)
    elif emotion == "angry":
        d.arc(B((cx - 16, 240, cx + 16, 256)), 200, 340, fill=OUT, width=4 * S)
    elif emotion == "surprised":
        d.ellipse(B((cx - 9, 226, cx + 9, 250)), fill=(120, 30, 30), outline=OUT, width=2 * S)
    elif emotion == "scared":
        d.ellipse(B((cx - 14, 230, cx + 14, 248)), fill=(120, 30, 30), outline=OUT, width=2 * S)
    else:
        d.line(P([(cx - 12, 236), (cx + 12, 236)]), fill=OUT, width=3 * S)

    # --- extras
    if "mustache" in ex:
        mc = (235, 235, 235) if "whitebeard" in ex else hair
        paint(img, PO([(cx, 218), (cx - 30, 222), (cx - 40, 234), (cx - 24, 229), (cx, 226),
                       (cx + 24, 229), (cx + 40, 234), (cx + 30, 222)]), mc)
    if "glasses" in ex:
        for sx in (-20, 20):
            d.ellipse(B((cx + sx - 17, 176, cx + sx + 17, 208)), outline=OUT, width=3 * S)
        d.line(P([(cx - 3, 192), (cx + 3, 192)]), fill=OUT, width=3 * S)
    if "wrinkles" in ex:
        for yy in (146, 153):
            d.arc(B((cx - 24, yy, cx + 24, yy + 14)), 200, 340, fill=sk_d, width=2 * S)
        d.arc(B((cx - 40, 205, cx - 22, 232)), 100, 260, fill=sk_d, width=2 * S)
        d.arc(B((cx + 22, 205, cx + 40, 232)), 280, 80, fill=sk_d, width=2 * S)
    if "bindi" in ex:
        d.ellipse(B((cx - 4, 162, cx + 4, 170)), fill=(200, 30, 40))
    if "blush" in ex:
        for sx in (-36, 36):
            d.ellipse(B((cx + sx - 11, 212, cx + sx + 11, 232)), fill=(235, 110, 110, 90))

    return img.resize((cw, ch), Image.LANCZOS)


_char_cache = {}


def get_char(face_id, dress, emotion):
    key = (face_id, dress["c1"], dress["c2"], dress["pat"], dress["lower"], emotion)
    if key not in _char_cache:
        _char_cache[key] = draw_character(face_id, dress, emotion)
    return _char_cache[key]


def pick_dresses(rng, n):
    """n unique (colour, colour2, pattern) combos"""
    out, seen = [], set()
    while len(out) < n:
        c1, c2 = rng.sample(PALETTE, 2)
        pat = rng.choice(PATTERNS)
        if (c1, pat) in seen:
            continue
        seen.add((c1, pat))
        out.append(dict(c1=c1, c2=c2, pat=pat, lower=rng.choice(LOWERS)))
    return out


# ------------------------------------------------------------------ backgrounds
class D:
    def __init__(self):
        self.img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 255))
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def rect(self, x0, y0, x1, y1, fill):
        self.d.rectangle(B((x0, y0, x1, y1)), fill=fill)

    def ell(self, x0, y0, x1, y1, fill):
        self.d.ellipse(B((x0, y0, x1, y1)), fill=fill)

    def poly(self, pts, fill):
        self.d.polygon(P(pts), fill=fill)

    def line(self, pts, fill, w=2):
        self.d.line(P(pts), fill=fill, width=max(1, int(w * S)))

    def grad(self, y0, y1, c0, c1):
        for y in range(int(y0 * S), int(y1 * S)):
            t = (y - y0 * S) / max(1, (y1 - y0) * S)
            self.d.line([(0, y), (W * S, y)], fill=lerp(c0, c1, t))

    def hills(self, base, color, amp, freq, phase):
        pts = [(x, base - amp * (math.sin(x * freq + phase) * 0.5 + 0.5)) for x in range(0, W + 20, 20)]
        self.poly(pts + [(W, 720), (0, 720)], color)

    def sun(self, x, y, r, color):
        for k in range(4, 0, -1):
            self.ell(x - r - k * 12, y - r - k * 12, x + r + k * 12, y + r + k * 12, color + (28,))
        self.ell(x - r, y - r, x + r, y + r, color + (255,))

    def cloud(self, x, y, s=1.0):
        for dx, dy, w, h in [(0, 0, 90, 40), (30, -18, 70, 44), (-30, -8, 60, 34), (60, 4, 70, 30)]:
            self.ell(x + dx * s - w * s / 2, y + dy * s - h * s / 2, x + dx * s + w * s / 2, y + dy * s + h * s / 2,
                     (255, 255, 255, 230))

    def hut(self, x, gy, w, h, wall, roof):
        self.rect(x - w / 2, gy - h, x + w / 2, gy, wall)
        self.rect(x - w * 0.12, gy - h * 0.6, x + w * 0.12, gy, (90, 60, 40))
        self.poly([(x - w / 2 - 14, gy - h), (x + w / 2 + 14, gy - h), (x, gy - h - h * 0.75)], roof)
        for i in range(-3, 4):
            self.line([(x + i * w / 8, gy - h - 2), (x + i * w / 14, gy - h - h * 0.6)], (0, 0, 0, 40), 2)

    def tree(self, x, gy, s, leaf=(50, 130, 60)):
        self.rect(x - 7 * s, gy - 90 * s, x + 7 * s, gy, (100, 68, 42))
        for dx, dy, r in [(0, -120, 48), (-34, -96, 38), (34, -96, 38), (0, -80, 40)]:
            self.ell(x + (dx - r) * s, gy + (dy - r) * s, x + (dx + r) * s, gy + (dy + r) * s, leaf + (255,))


def _finish(dd):
    return dd.img.convert("RGB").resize((W, H), Image.LANCZOS)


def bg_village_street():
    dd = D()
    dd.grad(0, 480, (120, 195, 235), (255, 238, 205))
    dd.sun(1060, 110, 46, (255, 225, 110))
    dd.cloud(260, 100, 1.2); dd.cloud(700, 70, 0.9)
    dd.hills(480, (126, 176, 104), 60, 0.006, 0.5)
    dd.hills(500, (96, 154, 82), 40, 0.011, 2.0)
    dd.rect(0, 500, W, H, (116, 170, 76))
    dd.poly([(520, 495), (760, 495), (1240, 720), (40, 720)], (208, 168, 118))
    dd.hut(170, 520, 150, 100, (214, 176, 130), (176, 130, 70))
    dd.hut(1090, 515, 170, 110, (230, 200, 150), (150, 98, 60))
    dd.tree(60, 540, 1.0); dd.tree(1230, 535, 1.1); dd.tree(430, 500, 0.7)
    return _finish(dd)


def bg_shop():
    dd = D()
    dd.grad(0, 480, (130, 200, 235), (255, 240, 210))
    dd.hills(470, (120, 172, 100), 50, 0.007, 1.0)
    dd.rect(0, 490, W, H, (120, 172, 80))
    dd.poly([(300, 500), (980, 500), (1280, 720), (0, 720)], (210, 170, 120))
    dd.hut(130, 500, 140, 95, (214, 176, 130), (176, 130, 70))
    dd.hut(1150, 500, 140, 95, (230, 200, 150), (150, 98, 60))
    dd.rect(342, 250, 356, 450, (90, 60, 40)); dd.rect(924, 250, 938, 450, (90, 60, 40))
    for i in range(12):
        x0 = 330 + i * 51
        dd.poly([(x0, 246), (x0 + 51, 246), (x0 + 51, 300), (x0, 300)], (200, 50, 50) if i % 2 == 0 else (250, 245, 235))
        dd.ell(x0, 285, x0 + 51, 315, (200, 50, 50) if i % 2 == 0 else (250, 245, 235))
    dd.rect(330, 450, 950, 570, (150, 95, 55)); dd.rect(320, 436, 960, 458, (110, 70, 40))
    dd.rect(520, 196, 760, 240, (240, 200, 60)); dd.rect(530, 206, 750, 230, (200, 60, 50))
    dd.ell(560, 396, 700, 446, (45, 45, 48)); dd.ell(572, 402, 688, 428, (90, 60, 40))
    dd.poly([(610, 395), (630, 340), (650, 395)], (255, 140, 40, 220))
    for x, c in [(400, (60, 150, 90)), (450, (220, 160, 40)), (780, (190, 60, 60)), (840, (80, 120, 200)), (890, (230, 120, 60))]:
        dd.ell(x - 24, 400, x + 24, 446, c)
    dd.line([(640, 246), (640, 330)], (60, 40, 30), 2); dd.ell(628, 330, 652, 354, (255, 230, 120, 255))
    return _finish(dd)


def bg_market():
    dd = D()
    dd.grad(0, 450, (135, 205, 238), (255, 240, 215))
    dd.hills(450, (126, 176, 104), 40, 0.008, 0.2)
    dd.rect(0, 470, W, H, (205, 170, 125))
    awn = [(210, 60, 60), (60, 140, 200), (240, 170, 40)]
    prod = [(220, 60, 50), (240, 140, 40), (80, 160, 70)]
    for i in range(3):
        x = 60 + i * 410
        dd.rect(x, 240, x + 8, 470, (90, 60, 40)); dd.rect(x + 312, 240, x + 320, 470, (90, 60, 40))
        for k in range(8):
            dd.poly([(x + k * 40, 230), (x + k * 40 + 40, 230), (x + k * 40 + 40, 290), (x + k * 40, 290)],
                    awn[i] if k % 2 == 0 else (250, 245, 235))
        dd.rect(x - 6, 400, x + 326, 480, (140, 95, 60))
        for k in range(7):
            for j in range(2):
                dd.ell(x + 8 + k * 44, 372 + j * 12, x + 46 + k * 44, 410 + j * 12, prod[i])
    return _finish(dd)


def bg_field():
    dd = D()
    dd.grad(0, 470, (255, 185, 115), (255, 236, 195))
    dd.sun(640, 440, 70, (255, 205, 100))
    dd.cloud(220, 110, 1.1); dd.cloud(980, 150, 1.0)
    dd.hills(470, (150, 160, 100), 50, 0.006, 1.2)
    dd.rect(0, 470, W, H, (100, 160, 62))
    for x in range(-1400, 2700, 110):
        dd.line([(640, 470), (x, 720)], (62, 124, 46), 7)
    dd.tree(90, 480, 0.8); dd.tree(1190, 478, 0.8)
    dd.hut(900, 478, 90, 60, (214, 176, 130), (176, 130, 70))
    return _finish(dd)


def bg_house_inside():
    dd = D()
    dd.rect(0, 0, W, 520, (226, 190, 140)); dd.rect(0, 520, W, H, (140, 95, 65))
    for x in range(0, W, 110):
        dd.line([(x, 520), (x - 40, 720)], (110, 72, 48), 3)
    dd.rect(880, 110, 1110, 320, (90, 60, 40)); dd.rect(894, 124, 1096, 306, (255, 235, 180))
    dd.line([(995, 124), (995, 306)], (90, 60, 40), 6); dd.line([(894, 215), (1096, 215)], (90, 60, 40), 6)
    dd.rect(90, 220, 230, 520, (120, 80, 50)); dd.rect(100, 232, 220, 520, (80, 54, 36))
    dd.rect(380, 420, 760, 450, (160, 110, 60))
    for x in (390, 740):
        dd.rect(x, 450, x + 14, 540, (120, 80, 50))
    for x in range(392, 756, 20):
        dd.line([(x, 420), (x, 450)], (230, 215, 190), 3)
    dd.line([(640, 0), (640, 110)], (60, 40, 30), 2); dd.ell(616, 110, 664, 158, (255, 220, 110, 255))
    dd.ell(590, 90, 690, 190, (255, 220, 110, 60))
    for x, s in [(1000, 1.0), (1100, 0.8)]:
        dd.ell(x - 45 * s, 560 - 90 * s + 0, x + 45 * s, 560 + 40 * s, (190, 95, 60))
    return _finish(dd)


def bg_night_village():
    dd = D()
    dd.grad(0, 480, (8, 12, 40), (40, 55, 105))
    rr = random.Random(3)
    for _ in range(70):
        x, y = rr.randint(0, W), rr.randint(0, 300)
        dd.ell(x, y, x + 3, y + 3, (255, 255, 230, 220))
    dd.sun(1060, 110, 42, (240, 240, 205))
    dd.hills(480, (22, 44, 52), 50, 0.006, 0.8)
    dd.rect(0, 490, W, H, (28, 56, 42))
    dd.poly([(520, 495), (760, 495), (1240, 720), (40, 720)], (70, 60, 55))
    for x, gy, w in [(420, 520, 130), (900, 515, 150), (1160, 520, 120)]:
        dd.hut(x, gy, w, 90, (80, 60, 50), (50, 38, 32))
        dd.rect(x - w * 0.3, gy - 70, x - w * 0.1, gy - 45, (255, 210, 90))
    dd.tree(130, 540, 1.7, (20, 60, 40))
    return _finish(dd)


def bg_haunted_tree():
    dd = D()
    dd.grad(0, 520, (10, 8, 28), (70, 50, 95))
    dd.sun(900, 150, 80, (232, 232, 200))
    dd.rect(0, 520, W, H, (32, 28, 40))
    dd.poly([(250, 540), (270, 330), (300, 250), (350, 250), (330, 330), (370, 540)], (28, 22, 26))
    for pts, w in [([(300, 260), (200, 190), (130, 120)], 14), ([(320, 270), (420, 180), (500, 130)], 14),
                   ([(310, 250), (310, 150), (330, 70)], 12), ([(200, 190), (160, 220), (110, 230)], 7),
                   ([(420, 180), (470, 210), (520, 215)], 7), ([(130, 120), (90, 90)], 6)]:
        dd.line(pts, (28, 22, 26), w)
    dd.ell(296, 380, 316, 400, (255, 220, 60)); dd.ell(326, 382, 346, 402, (255, 220, 60))
    for x, y in [(520, 110), (560, 140), (600, 100)]:
        dd.line([(x, y), (x + 10, y + 8), (x + 20, y)], (10, 10, 10), 3)
    for x in range(-100, W, 200):
        dd.ell(x, 520, x + 340, 600, (230, 230, 245, 38))
    return _finish(dd)


def bg_river():
    dd = D()
    dd.grad(0, 440, (125, 198, 236), (255, 240, 210))
    dd.sun(200, 120, 44, (255, 225, 110)); dd.cloud(640, 90, 1.1); dd.cloud(1000, 150, 0.9)
    dd.hills(440, (126, 176, 104), 55, 0.006, 2.2)
    dd.rect(0, 440, W, H, (116, 170, 76))
    dd.poly([(0, 470), (1280, 450), (1280, 580), (0, 620)], (70, 150, 200))
    for y in range(490, 590, 24):
        for x in range(30, 1280, 140):
            dd.line([(x, y), (x + 30, y - 6), (x + 60, y)], (200, 235, 250), 3)
    dd.tree(90, 480, 1.0); dd.tree(1210, 470, 1.0)
    dd.ell(-100, 640, 1400, 900, (96, 154, 70))
    return _finish(dd)


BG_FUNCS = dict(village_street=bg_village_street, shop=bg_shop, market=bg_market, field=bg_field,
                house_inside=bg_house_inside, night_village=bg_night_village,
                haunted_tree=bg_haunted_tree, river=bg_river)
_bg_cache = {}

POSITIONS = {1: [640], 2: [420, 860], 3: [270, 640, 1010], 4: [200, 470, 810, 1080]}


def render_scene(bg_name, present, cast_map):
    """present: [{'id': 'm3', 'emotion': 'sad'}]; cast_map: id -> {'dress': {...}}"""
    if bg_name not in BG_FUNCS:
        bg_name = "village_street"
    if bg_name not in _bg_cache:
        _bg_cache[bg_name] = BG_FUNCS[bg_name]()
    img = _bg_cache[bg_name].copy().convert("RGBA")
    present = present[:4]
    xs = POSITIONS[len(present)] if present else []
    for x, p in zip(xs, present):
        cid = p["id"]
        emo = p.get("emotion", "neutral")
        if emo not in EMOTIONS:
            emo = "neutral"
        ch = get_char(cid, cast_map[cid]["dress"], emo)
        sc = AGE_SCALE[FACES[cid]["age"]]
        ch = ch.resize((int(360 * sc), int(640 * sc)), Image.LANCZOS)
        gy = 655
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([x - 90 * sc, gy - 12, x + 90 * sc, gy + 14], fill=(0, 0, 0, 70))
        img = Image.alpha_composite(img, sh)
        img.alpha_composite(ch, (int(x - ch.width / 2), int(gy - 620 * sc)))
    return img.convert("RGB")


if __name__ == "__main__":
    rng = random.Random(7)
    ids = ["m5", "f4", "m2", "f1"]
    dr = pick_dresses(rng, 4)
    cm = {i: {"dress": d} for i, d in zip(ids, dr)}
    for bgn in BACKGROUNDS:
        render_scene(bgn, [{"id": i, "emotion": e} for i, e in zip(ids[:3], ["happy", "sad", "angry"])], cm).save(f"test_{bgn}.jpg")
    print("ok")
