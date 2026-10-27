"""Nexus Docs eindcontrole: test a montage BEFORE the user sees it.

usage:
  python3 -m pipeline.qa_check --words words.json (--shots shots.json | --capcut draft_info.json --beeldenlijst list.md)
                               [--video final.mp4] [--srt subs.srt] [--chapters chapters.json] [--out report.md]

Exit code 0 = no FAIL (warnings allowed), 1 = at least one FAIL.
"""
import argparse, json, re, subprocess, sys, os
from .common import load_json, load_words, find_phrase, parse_beeldenlijst, ts

# ---- rules (stijlgids) ----
SYNC_LATE = 0.35        # image may start at most this much AFTER its first word
SYNC_EARLY = 0.60       # ... and at most this much BEFORE it
STILL_MIN, STILL_WARN_MIN = 1.2, 1.8
STILL_WARN_MAX, STILL_MAX = 6.5, 8.5
CARD_MIN = 4.0
OUTRO_MIN = 6.0
TARGET_LUFS, LUFS_TOL = -14.0, 1.0
SILENCE_MAX = 2.5       # longest allowed silence in the mix outside chapter cards (s)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, area, msg, t=None):
        self.items.append((level, area, msg, t))

    def counts(self):
        return {l: sum(1 for i in self.items if i[0] == l) for l in ("FAIL", "WARN", "OK")}

    def markdown(self, title):
        c = self.counts()
        verdict = "❌ AFGEKEURD" if c["FAIL"] else ("⚠️ GOEDGEKEURD MET WAARSCHUWINGEN" if c["WARN"] else "✅ GOEDGEKEURD")
        out = [f"# Eindcontrole: {title}", "", f"**{verdict}** · {c['FAIL']} fouten · {c['WARN']} waarschuwingen", ""]
        for lvl, head in (("FAIL", "Fouten (eerst oplossen)"), ("WARN", "Waarschuwingen"), ("OK", "In orde")):
            rows = [i for i in self.items if i[0] == lvl]
            if not rows:
                continue
            out += [f"## {head}", ""]
            for _, area, msg, t in sorted(rows, key=lambda r: (r[1], r[3] if r[3] is not None else -1)):
                tt = f"`{ts(t)}` " if t is not None else ""
                out.append(f"- **{area}** {tt}{msg}")
            out.append("")
        return "\n".join(out)


# ---------------------------------------------------------------- shots
def shots_from_capcut(draft_path, beeldenlijst_md):
    d = load_json(draft_path)
    mats = {m["id"]: m for m in d["materials"]["videos"]}
    vt = [t for t in d["tracks"] if t["type"] == "video"][0]
    rows = parse_beeldenlijst(open(beeldenlijst_md).read()) if beeldenlijst_md else []
    stills = [r for r in rows if r["n"].isdigit()]
    shots = []
    for s in vt["segments"]:
        m = mats[s["material_id"]]
        name = os.path.basename(m["path"])
        st = s["target_timerange"]["start"] / 1e6
        du = s["target_timerange"]["duration"] / 1e6
        scales = [s["clip"]["scale"]["x"]]
        for kf in s.get("common_keyframes", []):
            if kf["property_type"] in ("KFTypeScaleX", "KFTypeScaleY"):
                scales += [k["values"][0] for k in kf["keyframe_list"]]
        mi = re.match(r"img-(\d+)", name)
        mc = re.match(r"card-(\d+)", name)
        if mi:
            idx = int(mi.group(1))
            row = stills[idx] if idx < len(stills) else None
            kind, n, anchor = "still", (row["n"] if row else f"img{idx}"), (row["anchor"] if row else None)
        elif mc:
            kind, n, anchor = "card", f"K{mc.group(1)}", None
        elif "outro" in name:
            kind, n, anchor = "outro", "O", None
        else:
            kind, n, anchor = "still", name, None
        shots.append({"n": n, "start": st, "end": st + du, "kind": kind, "src": m["path"], "anchor": anchor,
                      "w": m.get("width"), "h": m.get("height"), "min_scale": min(scales), "type": m.get("type"),
                      "zoom_range": max(scales) - min(scales)})
    shots.sort(key=lambda x: x["start"])
    return shots, d


# ---------------------------------------------------------------- checks
def check_sync(R, shots, words):
    idx, ok, missing = 0, 0, 0
    for s in shots:
        if s["kind"] != "still" or not s.get("anchor"):
            continue
        i = find_phrase(words, s["anchor"], idx, max_ahead=600)
        if i is None:
            missing += 1
            R.add("FAIL", "Beeld zonder stem", f"beeld {s['n']} (\"{s['anchor']}\") staat in de montage, maar die zin komt niet (meer) voor in de voice-over", s["start"])
            continue
        idx = i
        diff = s["start"] - words[i]["start"]
        if diff > SYNC_LATE:
            R.add("FAIL", "Sync", f"beeld {s['n']} komt {diff:.2f} s te laat (zin \"{s['anchor']}\" begint op {ts(words[i]['start'])})", s["start"])
        elif diff < -SYNC_EARLY:
            R.add("FAIL", "Sync", f"beeld {s['n']} komt {-diff:.2f} s te vroeg (zin \"{s['anchor']}\" begint op {ts(words[i]['start'])})", s["start"])
        else:
            ok += 1
    R.add("OK", "Sync", f"{ok} beelden lopen gelijk met de stem (marge -{SYNC_EARLY}/+{SYNC_LATE} s)")


def check_durations(R, shots):
    bad = 0
    for s in shots:
        d = s["end"] - s["start"]
        if s["kind"] == "still":
            moving = s.get("zoom_range", 0) >= 0.15     # a long camera move (e.g. zoom out over a route) may run longer
            if d > STILL_MAX and moving and d <= 12:
                R.add("WARN", "Beeldduur", f"beeld {s['n']} staat {d:.1f} s in beeld (lange camerabeweging)", s["start"])
            elif d < STILL_MIN or d > STILL_MAX:
                bad += 1; R.add("FAIL", "Beeldduur", f"beeld {s['n']} staat {d:.1f} s in beeld (toegestaan {STILL_MIN}–{STILL_MAX} s)", s["start"])
            elif d < STILL_WARN_MIN or d > STILL_WARN_MAX:
                R.add("WARN", "Beeldduur", f"beeld {s['n']} staat {d:.1f} s in beeld", s["start"])
        elif s["kind"] == "card" and d < CARD_MIN:
            bad += 1; R.add("FAIL", "Hoofdstukkaart", f"{s['n']} staat maar {d:.1f} s in beeld (minimaal {CARD_MIN} s)", s["start"])
        elif s["kind"] == "outro" and d < OUTRO_MIN:
            R.add("WARN", "Outro", f"outro duurt {d:.1f} s", s["start"])
    if not bad:
        R.add("OK", "Beeldduur", "alle beelden en hoofdstukkaarten hebben een goede duur")


def check_continuity(R, shots, total=None):
    bad = 0
    if shots and shots[0]["start"] > 0.05:
        bad += 1; R.add("FAIL", "Tijdlijn", f"de video begint met {shots[0]['start']:.2f} s zonder beeld", 0)
    for a, b in zip(shots, shots[1:]):
        g = b["start"] - a["end"]
        if g > 0.05:
            bad += 1; R.add("FAIL", "Tijdlijn", f"gat van {g:.2f} s zonder beeld na {a['n']}", a["end"])
        elif g < -0.05:
            bad += 1; R.add("FAIL", "Tijdlijn", f"{a['n']} en {b['n']} overlappen {-g:.2f} s", b["start"])
    if total and shots and shots[-1]["end"] < total - 0.1:
        bad += 1; R.add("FAIL", "Tijdlijn", f"beeld stopt op {ts(shots[-1]['end'])}, audio loopt tot {ts(total)}", shots[-1]["end"])
    if not bad:
        R.add("OK", "Tijdlijn", "geen gaten of overlappingen in het beeldspoor")


def check_borders_capcut(R, shots):
    bad = 0
    for s in shots:
        if not s.get("w") or s.get("type") == "video":
            continue
        ar = s["w"] / s["h"]
        need = 1.0
        if abs(ar - 16 / 9) > 0.005:
            # CapCut fits the image inside the canvas; it must be scaled up to cover
            need = max(ar / (16 / 9), (16 / 9) / ar)
        if s["min_scale"] < need - 0.002:
            bad += 1; R.add("FAIL", "Zwarte randen", f"beeld {s['n']} ({s['w']}×{s['h']}) zoomt tot {s['min_scale']:.3f}, nodig ≥ {need:.3f}", s["start"])
    if not bad:
        R.add("OK", "Zwarte randen", "alle beelden vullen het hele 16:9-kader")


def check_chapters(R, shots, chapters):
    cards = [s for s in shots if s["kind"] == "card"]
    if chapters is None:
        R.add("OK", "Hoofdstukken", f"{len(cards)} hoofdstukkaarten in de montage")
        return
    if len(cards) != len(chapters):
        R.add("FAIL", "Hoofdstukken", f"{len(cards)} hoofdstukkaarten in de montage, {len(chapters)} hoofdstukken in de planning")
    for c in chapters:
        near = [s for s in cards if abs(s["start"] - c["start"]) < 1.0]
        if not near:
            R.add("FAIL", "Hoofdstukken", f"hoofdstuk {c['n']} \"{c['title']}\" ({ts(c['start'])}) heeft geen kaart op die plek", c["start"])


def ff(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def check_video(R, path, shots):
    # loudness
    e = ff(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e); p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
    if m:
        lufs = float(m[-1])
        lvl = "OK" if abs(lufs - TARGET_LUFS) <= LUFS_TOL else "FAIL"
        R.add(lvl, "Volume", f"integrated loudness {lufs:.1f} LUFS (doel {TARGET_LUFS} ± {LUFS_TOL})")
    if p and float(p[-1]) > -0.5:
        R.add("WARN", "Volume", f"piek {p[-1]} dBFS (kan vervormen)")
    # silences (dips) outside chapter cards
    cards = [(s["start"] - 1.5, s["end"] + 1.5) for s in shots if s["kind"] in ("card", "outro")]
    e = ff(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", f"silencedetect=n=-45dB:d={SILENCE_MAX}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", e)]
    sil = 0
    for a, b in zip(starts, ends):
        if not any(c0 <= a <= c1 for c0, c1 in cards):
            sil += 1; R.add("FAIL", "Geluid", f"{b-a:.1f} s (bijna) stilte", a)
    if not sil:
        R.add("OK", "Geluid", f"geen stiltes langer dan {SILENCE_MAX} s buiten de hoofdstukkaarten")
    # black borders: cropdetect on sampled frames
    e = ff(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", "fps=1/2,cropdetect=limit=24:round=2:reset=1", "-f", "null", "-"])
    W, H = None, None
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                       capture_output=True, text=True).stdout.strip().split(",")
    W, H = int(r[0]), int(r[1])
    bad = set()
    for mm in re.finditer(r"t:([\d.]+).*?crop=(\d+):(\d+):(\d+):(\d+)", e):
        t, w, h = float(mm.group(1)), int(mm.group(2)), int(mm.group(3))
        if w < W - 8 or h < H - 8:
            bad.add(round(t))
    for t in sorted(bad)[:20]:
        R.add("FAIL", "Zwarte randen", "zwarte of lege rand in beeld", t)
    if not bad:
        R.add("OK", "Zwarte randen", "geen randen gevonden in de video (1 frame per 2 s gecontroleerd)")


def check_srt(R, path, words, total):
    txt = open(path, encoding="utf-8").read()
    cues = re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)\n(.+?)(?:\n\n|\Z)", txt, re.S)
    tos = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8]) + int(s[9:]) / 1000
    prev, bad = 0, 0
    for a, b, t in cues:
        a, b = tos(a), tos(b)
        if a < prev - 0.01:
            bad += 1; R.add("FAIL", "Ondertiteling", "ondertitels overlappen", a)
        if b - a < 0.4:
            R.add("WARN", "Ondertiteling", f"heel kort ondertitelblok ({b-a:.2f} s): \"{t.strip()[:30]}\"", a)
        if max(len(l) for l in t.split("\n")) > 45:
            R.add("WARN", "Ondertiteling", f"lange regel: \"{t.strip()[:45]}…\"", a)
        prev = b
    srt_words = len(re.findall(r"[\w']+", " ".join(c[2] for c in cues)))
    cov = srt_words / max(1, len(words))
    if cov < 0.95 or cov > 1.08:
        bad += 1; R.add("FAIL", "Ondertiteling", f"ondertiteling bevat {srt_words} woorden, de voice-over {len(words)} — klopt niet bij de VO")
    if cues and total and tos(cues[-1][1]) > total + 0.5:
        bad += 1; R.add("FAIL", "Ondertiteling", "laatste ondertitel loopt na het einde van de video")
    if not bad:
        R.add("OK", "Ondertiteling", f"{len(cues)} blokken, sluit aan op de voice-over")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--shots"); ap.add_argument("--capcut"); ap.add_argument("--beeldenlijst")
    ap.add_argument("--video"); ap.add_argument("--srt"); ap.add_argument("--chapters")
    ap.add_argument("--title", default="video"); ap.add_argument("--out")
    a = ap.parse_args(argv)
    R = Report()
    words = load_words(a.words)
    total = None
    if a.capcut:
        shots, d = shots_from_capcut(a.capcut, a.beeldenlijst)
        total = d["duration"] / 1e6
        check_borders_capcut(R, shots)
    else:
        shots = load_json(a.shots)
        shots.sort(key=lambda s: s["start"])
    if a.video:
        from .common import ffprobe_duration
        total = ffprobe_duration(a.video)
    check_sync(R, shots, words)
    check_durations(R, shots)
    check_continuity(R, shots, total)
    check_chapters(R, shots, load_json(a.chapters) if a.chapters else None)
    if a.video:
        check_video(R, a.video, shots)
    if a.srt:
        check_srt(R, a.srt, words, total)
    md = R.markdown(a.title)
    if a.out:
        open(a.out, "w").write(md)
    print(md)
    return 1 if R.counts()["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
