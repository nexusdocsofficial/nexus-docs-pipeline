"""Storyboard PDF for checkpoint 3: per still the image, its start time, row number and the VO line it covers.

usage: python3 -m pipeline.storyboard videos/NN/prompts.json videos/NN/words.json videos/NN/beeld-bestanden.json \
           IMAGE_ROOT OUT.pdf [--title "05 Russia"]
  beeld-bestanden.json : {"<row n>": "<folder>/<file>.jpeg"} relative to IMAGE_ROOT
  Rows without an image (outro) are skipped. 2 columns x 4 rows per A4-landscape-ish page.
"""
import sys, os, argparse, textwrap
from PIL import Image, ImageDraw, ImageFont
from .common import load_json, load_words

FONT = os.path.join(os.path.dirname(__file__), "..", "fonts")


def font(size, bold=False):
    for p in ([os.path.join(FONT, "Inter-ExtraBold.otf")] if bold else []) + [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def vo_line(words, s, e):
    return " ".join(w["w"] for w in words if s - 0.05 <= w["start"] < e - 0.05)


def build(prompts_f, words_f, files_f, root, out, title=""):
    prompts, words, files = load_json(prompts_f), load_words(words_f), load_json(files_f)
    items = [p for p in prompts if p["n"] in files and p["start"] is not None]
    W, H, cols, rows = 2480, 1754, 2, 4
    tw = (W - 3 * 60) // cols
    th = int(tw * 9 / 16 * 0.62)
    th_w = int(th * 16 / 9)
    cell_h = (H - 140) // rows
    f_t, f_b, f_h = font(30, True), font(26), font(40, True)
    pages, k = [], 0
    while k < len(items):
        pg = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(pg)
        d.text((60, 40), f"{title}  ·  storyboard  ·  page {len(pages) + 1}", fill="black", font=f_h)
        for slot in range(cols * rows):
            if k >= len(items):
                break
            p = items[k]; k += 1
            x = 60 + (slot % cols) * (tw + 60); y = 120 + (slot // cols) * cell_h
            try:
                im = Image.open(os.path.join(root, files[p["n"]])).convert("RGB")
                im = im.resize((th_w, th))
                pg.paste(im, (x, y))
            except Exception as e:  # missing image shows as grey box
                d.rectangle([x, y, x + th_w, y + th], fill="#ddd"); d.text((x + 20, y + 20), str(e)[:60], fill="red", font=f_b)
            s = p["start"]; tx = x + th_w + 24
            d.text((tx, y), f"#{p['n']}   {int(s // 60)}:{s % 60:04.1f}  ({p['dur']:.1f}s)", fill="black", font=f_t)
            line = vo_line(words, p["start"], p["end"])
            wrap = textwrap.wrap(f"“{line}”", width=max(20, (tw - th_w - 30) // 14))
            for i, l in enumerate(wrap[:9]):
                d.text((tx, y + 46 + i * 34), l, fill="#333", font=f_b)
        pages.append(pg)
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=200)
    print(f"{len(items)} beelden, {len(pages)} pagina's -> {out}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("prompts"); a.add_argument("words"); a.add_argument("files"); a.add_argument("root"); a.add_argument("out")
    a.add_argument("--title", default="")
    x = a.parse_args()
    build(x.prompts, x.words, x.files, x.root, x.out, x.title)
