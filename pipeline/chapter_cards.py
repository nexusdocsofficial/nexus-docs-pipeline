"""Chapter cards in the Nexus Docs house style: a parchment plaque at the top with 'CHAPTER ONE' (rust),
a small divider with the gold star from the logo, and the title in dark brown hand lettering (Patrick Hand).
The plaque has a soft shadow and a double border, like the plaques on the map cards of videos 3 and 4.

usage: python3 -m pipeline.chapter_cards IN.jpg OUT.jpg 1 "The Frozen Doors"
       (image is first cropped/resized to exactly 1920x1080)
"""
import sys, os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', 'PatrickHand-Regular.ttf')
NUM = ['ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'TEN']
PARCH, EDGE, INNER = (243, 230, 198, 255), (70, 45, 25, 255), (150, 110, 70, 255)
RUST, INK, GOLD = (165, 70, 20), (35, 22, 12), (242, 182, 50)


def fit16x9(im):
    im = im.convert('RGB'); w, h = im.size; r = W / H
    if w / h > r:
        nw = int(h * r); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    elif w / h < r:
        nh = int(w / r); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((W, H), Image.LANCZOS)


def star(d, cx, cy, r, fill):
    pts = []
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.32
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=(90, 60, 10))


def font_fit(d, txt, maxw, size):
    while size > 30:
        f = ImageFont.truetype(FONT, size)
        if d.textlength(txt, font=f) <= maxw:
            return f
        size -= 2
    return ImageFont.truetype(FONT, size)


def card(src, out, n, title):
    im = fit16x9(Image.open(src)).convert('RGBA')
    d0 = ImageDraw.Draw(im)
    t1 = f'CHAPTER {NUM[n] if n < len(NUM) else n}'
    t2 = title.upper()
    f1 = ImageFont.truetype(FONT, 50)
    f2 = font_fit(d0, t2, 1100, 104)
    pw = max(d0.textlength(t2, font=f2), d0.textlength(t1, font=f1)) + 150
    pw = max(pw, 620)
    x0, x1 = W / 2 - pw / 2, W / 2 + pw / 2
    y0, y1 = 46, 46 + 266
    # shadow
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle([x0 + 8, y0 + 12, x1 + 8, y1 + 12], radius=30, fill=(0, 0, 0, 110))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(9)))
    pl = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(pl)
    d.rounded_rectangle([x0, y0, x1, y1], radius=30, fill=PARCH, outline=EDGE, width=6)
    d.rounded_rectangle([x0 + 14, y0 + 14, x1 - 14, y1 - 14], radius=20, outline=INNER, width=2)
    im = Image.alpha_composite(im, pl)
    d = ImageDraw.Draw(im)
    w1 = d.textlength(t1, font=f1)
    d.text((W / 2 - w1 / 2, y0 + 20), t1, font=f1, fill=RUST, stroke_width=1, stroke_fill=RUST)
    # divider with the gold star
    yy = y0 + 104
    d.line([(W / 2 - 150, yy), (W / 2 - 30, yy)], fill=INNER, width=3)
    d.line([(W / 2 + 30, yy), (W / 2 + 150, yy)], fill=INNER, width=3)
    star(d, W / 2, yy, 17, GOLD)
    w2 = d.textlength(t2, font=f2)
    d.text((W / 2 - w2 / 2, y0 + 118), t2, font=f2, fill=INK, stroke_width=1, stroke_fill=INK)
    im.convert('RGB').save(out, quality=94)


if __name__ == '__main__':
    card(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
