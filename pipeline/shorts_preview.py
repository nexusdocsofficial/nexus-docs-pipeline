"""Optional preview per Short (only when Thijs asks for one; the Shorts flow itself needs no approval).

For each Short: one overview image (6 frames + title + first/last sentence + upload moment)
and a light 480p preview clip that plays fine on a phone.

usage: python3 -m pipeline.shorts_preview videos/NN/shorts-upload.json OUT_DIR A=a.mp4 B=b.mp4 C=c.mp4
       (shorts-upload.json may hold "first_line"/"last_line" per Short; otherwise they are left out)
"""
import sys, os, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFont
from .common import load_json, ffprobe_duration
from .upload_folder import nice

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except OSError:
        return ImageFont.load_default()


def frames(mp4, n=6, h=480):
    d = ffprobe_duration(mp4)
    out = []
    for k in range(n):
        t = d * (0.04 + 0.92 * k / (n - 1))
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1",
                            "-vf", f"scale=-2:{h}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True)
        from io import BytesIO
        out.append((t, Image.open(BytesIO(r.stdout)).convert("RGB")))
    return out, d


def sheet(sid, s, mp4, path):
    fr, dur = frames(mp4)
    fw, fh = fr[0][1].size
    pad, head = 16, 210
    W = pad + len(fr) * (fw + pad)
    H = head + fh + 60 + pad
    img = Image.new("RGB", (W, H), (15, 20, 30))
    d = ImageDraw.Draw(img)
    when, _ = nice(s["upload"])
    d.text((pad, 14), f"SHORT {sid}  ·  {dur:.0f} sec  ·  upload {when}", font=font("Inter-ExtraBold.otf", 30), fill=(34, 211, 238))
    d.text((pad, 58), s["title"], font=font("Inter-Black.otf", 34), fill=(255, 255, 255))
    y = 108
    for label, key in (("Begint met", "first_line"), ("Eindigt met", "last_line")):
        if s.get(key):
            d.text((pad, y), f"{label}: “{textwrap.shorten(s[key], 120)}”", font=font("Inter-ExtraBold.otf", 22), fill=(255, 210, 31))
            y += 34
    for k, (t, im) in enumerate(fr):
        x = pad + k * (fw + pad)
        img.paste(im, (x, head))
        d.text((x, head + fh + 10), f"{int(t // 60)}:{t % 60:04.1f}", font=font("Inter-ExtraBold.otf", 22), fill=(200, 200, 200))
    img.save(path, quality=88)


def clip(mp4, path):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp4, "-vf", "scale=-2:854", "-c:v", "libx264", "-crf", "28",
                    "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", path], check=True)


if __name__ == "__main__":
    cfg = load_json(sys.argv[1])["shorts"]
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for arg in sys.argv[3:]:
        sid, mp4 = arg.split("=", 1)
        sheet(sid, cfg[sid], mp4, os.path.join(out, f"voorbeeld-{sid}.jpg"))
        clip(mp4, os.path.join(out, f"voorbeeld-{sid}.mp4"))
        print("preview", sid)
