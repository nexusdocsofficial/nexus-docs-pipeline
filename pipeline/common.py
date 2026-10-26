"""Shared helpers for the Nexus Docs pipeline.

Standard data per video (in videos/NN-name/):
  words.json     list of {"w": str, "start": float, "end": float}   - word timing on the FINAL timeline
  shots.json     list of {"n": str, "start", "end", "kind": "still|card|outro", "src": path,
                          "anchor": "first words of the VO line" | null}
  chapters.json  list of {"n": int, "title": str, "start": float}
  video.json     {"id": "04", "title": ..., "upload": "YYYY-MM-DD HH:MM", "capcut_name": ..., "media_dir": ...}
"""
import json, re, subprocess, os

norm = lambda w: re.sub(r"[^\w]", "", w.lower().replace("’", "'"))


def load_json(p):
    with open(p) as f:
        return json.load(f)


def save_json(obj, p):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def load_words(p):
    """Accept our own format, or a Creative Claw / ElevenLabs Scribe transcript (diarization json)."""
    d = load_json(p)
    if isinstance(d, dict) and "words" in d:
        d = [x for x in d["words"] if x.get("type", "word") == "word"]
    out = []
    for x in d:
        out.append({"w": x.get("w", x.get("text")), "start": float(x["start"]), "end": float(x["end"])})
    return out


def find_phrase(words, phrase, start_idx=0, max_ahead=None):
    """Index of the first word of `phrase` at/after start_idx (fuzzy: first 3 normalised tokens)."""
    # numbers are skipped: transcripts often write "2025" as "twenty twenty-five"
    raw = [norm(t) for t in phrase.split() if norm(t)]
    lead_num = bool(raw) and raw[0].isdigit()
    toks = [t for t in raw if not t.isdigit()][:3]
    if not toks:
        return None
    end = len(words) if max_ahead is None else min(len(words), start_idx + max_ahead)
    W = [norm(w["w"]) for w in words]

    def match_from(i, toks, gap):
        j = i
        for t in toks[1:]:
            for k in range(j + 1, min(j + 1 + gap, len(W))):
                if W[k] == t:
                    j = k
                    break
            else:
                return False
        return True

    for ntok, gap in ((len(toks), 1), (len(toks), 5), (min(2, len(toks)), 5)):
        for i in range(start_idx, end):
            if W[i] == toks[0] and match_from(i, toks[:ntok], gap):
                return i
    if lead_num:  # phrase starts with a number: return the word before the first matched token
        return None
    return None


def ffprobe_duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def ts(t, srt=False):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    if srt:
        ms = int(round((s - int(s)) * 1000))
        if ms == 1000:
            ms = 999
        return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"
    return f"{m}:{s:04.1f}" if h == 0 else f"{h}:{m:02d}:{s:04.1f}"


def parse_beeldenlijst(md_text):
    """Parse a beeldenlijst markdown table into rows {n, anchor, type}. Row ids: 1..N, K1.., O."""
    rows, ia, it = [], 2, 3
    for line in md_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "#":           # header: find the VO and type columns
            low = [c.lower() for c in cells]
            ia = next((i for i, c in enumerate(low) if "vo" in c or "voice" in c), ia)
            it = next((i for i, c in enumerate(low) if c == "type"), it)
            continue
        if len(cells) <= max(ia, it) or not re.match(r"^(\d+|K\d+|O)$", cells[0]):
            continue
        anchor = cells[ia].strip("*")
        rows.append({"n": cells[0], "anchor": None if anchor.lower().startswith("chapter") else anchor,
                     "type": cells[it]})
    return rows
