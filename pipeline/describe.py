"""YouTube upload package for a long video: description with chapters, tags and settings.

usage: python3 -m pipeline.describe videos/NN-name/video.json videos/NN-name/chapters.json out.md

video.json fields used:
  title, hook (2-3 sentences), summary (1 paragraph), sources [str], hashtags [str], tags [str],
  upload ("YYYY-MM-DD HH:MM" Europe/Amsterdam), pinned_comment, thumbnail
Chapters: the first chapter must start at 0:00 (YouTube rule); an intro is added automatically.
"""
import sys
from .common import load_json

FOOTER = "🔔 Nexus Docs explains the big stories behind geography, history and power, simply. Subscribe for more."


def chapter_lines(chapters):
    def mmss(t):
        t = int(round(t))
        return f"{t // 60}:{t % 60:02d}"
    out = []
    if not chapters or chapters[0]["start"] > 1:
        out.append("0:00 Intro")
    for c in chapters:
        out.append(f"{mmss(c['start'])} {c['title']}")
    return out


def build(v, chapters):
    desc = [v["hook"], "", v["summary"], "", "⏱️ Chapters", *chapter_lines(chapters), ""]
    if v.get("sources"):
        desc += ["📚 Sources", *[f"• {s}" for s in v["sources"]], ""]
    desc += [FOOTER, "", " ".join("#" + h.lstrip("#") for h in v.get("hashtags", []))]
    desc_txt = "\n".join(desc).strip()
    md = [f"# Uploadpakket: {v['title']}", "",
          f"**Titel:** {v['title']}  ",
          f"**Upload:** {v.get('upload', '?')} (NL-tijd), zichtbaarheid *Inplannen*  ",
          f"**Thumbnail:** `{v.get('thumbnail', '?')}`  ",
          "**Instellingen:** niet voor kinderen · categorie Onderwijs · videotaal Engels · ondertiteling: SRT uploaden (Engels)  ",
          f"**Tags:** {', '.join(v.get('tags', []))}", "",
          "## Beschrijving (plakken)", "", "```", desc_txt, "```", ""]
    if v.get("pinned_comment"):
        md += ["## Vastgezette reactie", "", v["pinned_comment"], ""]
    md += ["Let op: geen links in de beschrijving zolang het kanaal geen externe links mag plaatsen."]
    if len(desc_txt) > 5000:
        md.append("\n**WAARSCHUWING: beschrijving is langer dan 5000 tekens.**")
    return "\n".join(md)


if __name__ == "__main__":
    v, ch = load_json(sys.argv[1]), load_json(sys.argv[2])
    out = build(v, ch)
    open(sys.argv[3], "w").write(out)
    print(out)
