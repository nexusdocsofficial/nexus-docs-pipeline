"""Upload folders: the videos plus ONE text file to copy everything from.

Long video:
  python3 -m pipeline.upload_folder long videos/NN/video.json videos/NN/chapters.json OUT_DIR
          [--video final.mp4] [--srt subs.srt] [--thumbs a.jpg b.jpg]
  -> OUT_DIR/ video.mp4 (or export note), thumbnail.jpg (+B, C), ondertiteling-en.srt, KOPIEER-MIJ.txt

Shorts (final delivery; made autonomously, no approval step):
  python3 -m pipeline.upload_folder shorts videos/NN/video.json videos/NN/shorts-upload.json OUT_DIR A=a.mp4 B=b.mp4 C=c.mp4
  -> OUT_DIR/ "A - za 24 okt 17.00.mp4", "B - ...", "C - ...", KOPIEER-MIJ.txt

KOPIEER-MIJ.txt: per video blocks TITEL / BESCHRIJVING / TAGS / VASTGEZETTE REACTIE / INSTELLINGEN,
each block between clear lines, so one triple-click or drag selects exactly what to paste.
"""
import argparse, os, shutil, datetime
from .common import load_json
from .describe import chapter_lines, FOOTER

DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
LINE = "─" * 60


def nice(when):
    d = datetime.datetime.strptime(when, "%Y-%m-%d %H:%M")
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d:%H:%M}", f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d:%H.%M}"


def long_description(v, chapters):
    desc = [v["hook"], "", v["summary"], "", "⏱️ Chapters", *chapter_lines(chapters), ""]
    if v.get("sources"):
        desc += ["📚 Sources", *[f"• {s}" for s in v["sources"]], ""]
    desc += [FOOTER, "", " ".join("#" + h.lstrip("#") for h in v.get("hashtags", []))]
    return "\n".join(desc)


def block(name, text):
    return f"{LINE}\n▼ {name}\n{LINE}\n{text.strip()}\n"


def settings(when, extra):
    w, _ = nice(when)
    return "\n".join([f"Inplannen: {w} (NL-tijd)", "Doelgroep: Nee, niet gemaakt voor kinderen",
                      "Categorie: Onderwijs", "Taal video: Engels", *extra])


def long_folder(v, chapters, out, video=None, srt=None, thumbs=()):
    os.makedirs(out, exist_ok=True)
    if video:
        shutil.copy(video, os.path.join(out, "video.mp4"))
    for i, t in enumerate(thumbs):
        shutil.copy(t, os.path.join(out, "thumbnail.jpg" if i == 0 else f"thumbnail-{chr(65 + i)}.jpg"))
    if srt:
        shutil.copy(srt, os.path.join(out, "ondertiteling-en.srt"))
    w, _ = nice(v["upload"])
    txt = [f"LANGE VIDEO · {v['title']}", f"Upload: {w} (NL-tijd)", "",
           "Stappen: Studio → Maken → Video's uploaden → video.mp4 → plak hieronder per veld → thumbnail.jpg → "
           "'Meer weergeven' voor de tags → ondertiteling-en.srt bij Ondertitels → inplannen.", ""]
    if not video:
        txt += [f"! Exporteer eerst in CapCut (project \"{v.get('capcut_name', '?')}\") naar deze map als video.mp4 (1080p, 30 fps).", ""]
    txt += [block("TITEL", v["title"]), block("BESCHRIJVING", long_description(v, chapters)),
            block("TAGS", ", ".join(v.get("tags", []))),
            block("VASTGEZETTE REACTIE (na publicatie plaatsen en vastzetten)", v.get("pinned_comment", "")),
            block("INSTELLINGEN", settings(v["upload"], ["Ondertitels: Toevoegen → Bestand uploaden → ondertiteling-en.srt (Engels, met tijdcodes)",
                                                         "Eindscherm: 'Video' (nieuwste) + 'Abonneren' op de laatste 8 seconden"]))]
    open(os.path.join(out, "KOPIEER-MIJ.txt"), "w", encoding="utf-8").write("\n".join(txt))
    return out


def shorts_folder(v, S, out, files):
    os.makedirs(out, exist_ok=True)
    txt = [f"SHORTS · bij: {v['title']}", "",
           "Per Short: Studio → Maken → Video's uploaden → de mp4 → plak de velden → 'Meer weergeven' voor de tags →",
           "'Gerelateerde video' = de lange video → thumbnail: kies het genoemde frame → inplannen. Geen ondertitelbestand uploaden.", ""]
    for sid, s in S["shorts"].items():
        w, fn = nice(s["upload"])
        name = f"{sid} - {fn}.mp4"
        if sid in files:
            shutil.copy(files[sid], os.path.join(out, name))
        txt += ["", "█" * 60, f"SHORT {sid}  ·  bestand: {name}  ·  upload {w}", "█" * 60,
                block("TITEL", s["title"]), block("BESCHRIJVING", s["description"]),
                block("TAGS", ", ".join(s.get("tags", []))),
                block("VASTGEZETTE REACTIE (na publicatie)", s["pinned_comment"]),
                *([block("INSTAGRAM-TEKST (Reel, dag na YouTube)", s["instagram"])] if s.get("instagram") else []),
                block("INSTELLINGEN", settings(s["upload"], [f"Gerelateerde video: {v['title']}",
                                                             f"Thumbnail: frame rond {s.get('frame', '0:05')}"]))]
    open(os.path.join(out, "KOPIEER-MIJ.txt"), "w", encoding="utf-8").write("\n".join(txt))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    l = sub.add_parser("long"); l.add_argument("video_json"); l.add_argument("chapters_json"); l.add_argument("out")
    l.add_argument("--video"); l.add_argument("--srt"); l.add_argument("--thumbs", nargs="*", default=[])
    s = sub.add_parser("shorts"); s.add_argument("video_json"); s.add_argument("shorts_json"); s.add_argument("out")
    s.add_argument("files", nargs="*")
    a = ap.parse_args(argv)
    v = load_json(a.video_json)
    if a.mode == "long":
        print(long_folder(v, load_json(a.chapters_json), a.out, a.video, a.srt, a.thumbs))
    else:
        print(shorts_folder(v, load_json(a.shorts_json), a.out, dict(x.split("=", 1) for x in a.files)))


if __name__ == "__main__":
    main()
