"""Beeldenlijst from a row file: times from words.json, Flow prompts from the style guide templates.

input  videos/NN/beelden.json : {"style": {...optional overrides}, "rows": [
          {"n": "1", "anchor": "Russia is the biggest", "type": "kaart|concept|scene|label|tijdlijn|drama|card|outro",
           "beeld": "English scene description", "era": "none|now|1700|none@1905|...", "ref": ["path or n"]}]}
       era "none@1905" = no people, but ships/buildings/icons must fit 1905. Use it for EVERY historical row
       that shows ships, buildings or vehicles (also maps with ship icons).
output videos/NN/beeldenlijst.md   (| # | Tijd | VO begint met | Type | Beeld |) - readable by qa_check
       videos/NN/prompts.json      [{n, start, end, dur, prompt, refs}]
Warnings for stills shorter than 1.8 s or longer than 6.5 s, and anchors not found.

usage: python3 -m pipeline.beeldenlijst videos/NN/beelden.json videos/NN/words.json
"""
import sys, os, json
from .common import load_json, save_json, load_words, find_phrase

BASE = ("Hand-drawn cartoon illustration, 16:9, full frame, no borders. Simple stickman characters with round white heads, "
        "thick black outlines, simple facial expressions. Clean bold lines, flat vibrant colors, soft shading. Simple flat "
        "cartoon backgrounds, not realistic; every stickman has a visible simple face. Only show flags that are explicitly described.")
TYPES = {
    "scene": "Fully colored background scene drawn in simple flat cartoon shapes: {b} Warm, rich colors, storybook documentary feel.",
    "concept": "Plain pure white background, no scenery. Minimal composition: {b} Only the essential elements, lots of white space.",
    "kaart": "Illustrated map on a beige parchment background with soft blue seas, hand-drawn style with clear colored regions: {b} Readable, simple, no small text.",
    "label": "{b} Bold black hand-lettered text on a parchment scroll banner.",
    "tijdlijn": "Beige parchment background with a horizontal hand-drawn timeline showing small icons of eras. {b}",
    "drama": "Dark charcoal background with red glowing cracks. {b}",
    "card": "{b} Leave the upper third calm and simple (title text will be added later). No text in the image.",
}
NOPEOPLE = "No people or stickmen in the image."
ERAS = {
    "none": NOPEOPLE,
    "now": "Present day: modern clothing, modern ships and objects.",
}


def era_text(e):
    if "@" in e:   # e.g. "none@1905": no people, but ships/buildings must fit the period
        base, period = e.split("@", 1)
        if period in ("now", "the present day"):
            return era_text(base) + " Present day: any ships, buildings and icons are modern."
        return (era_text(base) + f" HISTORICAL ACCURACY, this is {period}: all ships, weapons and buildings "
                f"(also small icons) are authentic for that time, no modern ships or objects.")
    if e in ERAS:
        return ERAS[e]
    return (f"HISTORICAL ACCURACY, this scene takes place in {e}: all clothing, ships, weapons and buildings are authentic "
            f"for that time. No modern clothes, no modern long neckties, no modern objects.")


def build(rows_file, words_file):
    d = load_json(rows_file)
    rows, words = d["rows"], load_words(words_file)
    out_dir = os.path.dirname(rows_file)
    idx, starts, warn = 0, [], []
    for r in rows:
        if r["type"] == "outro":
            i = find_phrase(words, r["anchor"], idx)
        else:
            i = find_phrase(words, r["anchor"], idx, max_ahead=120)
        if i is None:
            warn.append(f"anker niet gevonden: {r['n']} '{r['anchor']}'")
            starts.append(None)
            continue
        idx = i
        starts.append(words[i]["start"])
    end_audio = words[-1]["end"] + 0.6
    prompts, md = [], ["| # | Tijd | VO begint met | Type | Beeld |", "|---|---|---|---|---|"]
    for k, r in enumerate(rows):
        s = starts[k]
        nxt = next((x for x in starts[k + 1:] if x is not None), end_audio)
        dur = None if s is None else nxt - s
        if dur is not None and r["type"] not in ("card", "outro") and (dur < 1.8 or dur > 6.5):
            warn.append(f"duur {r['n']}: {dur:.1f} s ('{r['anchor']}')")
        t = "?" if s is None else f"{int(s // 60)}:{s % 60:04.1f}"
        anchor = f"*{r['anchor']}*" if r["type"] == "card" else r["anchor"]
        md.append(f"| {r['n']} | {t} | {anchor} | {r['type']} | {r['beeld']} |")
        if r["type"] == "outro":
            continue
        body = TYPES[r["type"]].format(b=r["beeld"].rstrip(".") + ".")
        e = r.get("era", "none")
        era = NOPEOPLE if r["type"] in ("kaart", "tijdlijn", "drama", "label") and e == "none" else era_text(e)
        prompts.append({"n": r["n"], "start": s, "end": nxt, "dur": dur, "refs": r.get("ref", []),
                        "prompt": f"{BASE} {body} {era}"})
    open(os.path.join(out_dir, "beeldenlijst.md"), "w").write("\n".join(md) + "\n")
    save_json(prompts, os.path.join(out_dir, "prompts.json"))
    stills = [p for p in prompts if p["dur"] and rows[[r["n"] for r in rows].index(p["n"])]["type"] != "card"]
    print(f"{len(rows)} rijen, {len(stills)} stills, gem. {sum(p['dur'] for p in stills)/max(1,len(stills)):.1f} s")
    for w in warn:
        print("!", w)
    return prompts, warn


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
