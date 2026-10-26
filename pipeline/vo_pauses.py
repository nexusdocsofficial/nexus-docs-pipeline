"""Add breathing room to a single-take voice-over (style guide 1b).

Inserts silence at every paragraph boundary of the script, cut at the REAL silence in the audio
(quietest 20 ms window between the two words), never at the raw timestamps:
  - after a normal paragraph:              --para  (default 0.7 s)
  - before and after a chapter announcement ("Chapter one. ..."): --chapter (default 1.8 s)
Writes the new audio and words.json on the new timeline (our format: w/start/end).
Word timestamps from the TTS can be 0.3-0.5 s late: re-transcribe the result (Creative Claw `transcribe`)
for exact timing before building the edit. Every cut gets a 10 ms fade (no clicks).

usage: python3 -m pipeline.vo_pauses script.txt raw.mp3 raw-words.json OUT.mp3 OUT-words.json
       script.txt = the exact text sent to the TTS, paragraphs separated by a blank line.
       raw-words.json = Creative Claw result ({"words": [{text,startSeconds,endSeconds}]}) or our format.
"""
import sys, json, re, difflib, subprocess, tempfile, os
import numpy as np
from .common import norm, save_json

SR = 44100


def load_tts_words(p):
    d = json.load(open(p))
    if isinstance(d, dict):
        d = d.get("words") or d.get("wordTimings")
    return [{"w": x.get("w", x.get("text")), "start": float(x.get("start", x.get("startSeconds"))),
             "end": float(x.get("end", x.get("endSeconds")))} for x in d]


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32)


def frames_db(a, t0, t1, hop=0.01):
    i0, i1, h = max(0, int(t0 * SR)), min(len(a), int(t1 * SR)), int(hop * SR)
    out = []
    for i in range(i0, i1 - h, h):
        s = a[i:i + h]
        out.append((i / SR, 20 * np.log10(np.sqrt((s ** 2).mean()) / 32768 + 1e-9)))
    return out


def quietest(a, end, nxt, before=0.9, after=0.4, thresh=-50.0):
    """Cut point in the REAL silence between two words.

    TTS word timestamps can be 0.3-0.5 s late, so search a wide window around the boundary,
    take the longest run of frames below `thresh` dBFS (ties: closest to the boundary), cut in its middle.
    Returns (time, run_length_seconds)."""
    fr = frames_db(a, end - before, nxt + after)
    runs, cur = [], None
    for t, d in fr:
        if d < thresh:
            cur = [t, t + 0.01] if cur is None else [cur[0], t + 0.01]
        elif cur is not None:
            runs.append(cur); cur = None
    if cur is not None:
        runs.append(cur)
    if not runs:
        t, _ = min(fr, key=lambda x: x[1])
        return t + 0.005, 0.0
    mid = (end + nxt) / 2
    best = max(runs, key=lambda r: (round(r[1] - r[0], 2), -abs((r[0] + r[1]) / 2 - mid)))
    return (best[0] + best[1]) / 2, best[1] - best[0]


def fade(x, n, out):
    n = min(n, len(x))
    if n:
        r = np.linspace(1, 0, n) if out else np.linspace(0, 1, n)
        x = x.copy()
        if out:
            x[-n:] *= r
        else:
            x[:n] *= r
    return x


def paragraph_ends(paras, words):
    """Index (in words) of the last word of each paragraph, via sequence matching on normalised tokens."""
    stoks, owner = [], []
    for k, p in enumerate(paras):
        for t in p.split():
            for part in re.split(r"[-–—]", t):
                if norm(part):
                    stoks.append(norm(part)); owner.append(k)
    wtoks, wowner = [], []
    for i, w in enumerate(words):
        for part in re.split(r"[-–—]", w["w"]):
            if norm(part):
                wtoks.append(norm(part)); wowner.append(i)
    sm = difflib.SequenceMatcher(None, stoks, wtoks, autojunk=False)
    s2w = {}
    for a, b, n in sm.get_matching_blocks():
        for j in range(n):
            s2w[a + j] = wowner[b + j]
    ends = []
    for k in range(len(paras)):
        idx = [s2w[i] for i, o in enumerate(owner) if o == k and i in s2w]
        ends.append(max(idx) if idx else None)
    return ends


def main(script, raw_audio, raw_words, out_audio, out_words, para=0.7, chapter=1.8):
    paras = [p.strip() for p in open(script).read().split("\n\n") if p.strip()]
    words = load_tts_words(raw_words)
    ends = paragraph_ends(paras, words)
    a = decode(raw_audio)
    is_ch = [bool(re.match(r"chapter \w+\.", p.lower())) for p in paras]
    cuts = []  # (time, pause)
    for k in range(len(paras) - 1):
        e = ends[k]
        if e is None or e + 1 >= len(words):
            continue
        pause = chapter if (is_ch[k] or is_ch[k + 1]) else para
        t, run = quietest(a, words[e]["end"], words[e + 1]["start"])
        if run < 0.06:
            print(f"! weinig stilte na '{words[e]['w']}' ({run*1000:.0f} ms) rond {words[e]['end']:.2f}s")
        cuts.append((t, pause, e))
    pieces, last, shift, out = [], 0, 0.0, []
    wi = 0
    F = int(0.01 * SR)
    for t, pause, e in cuts:
        pieces.append(fade(fade(a[int(last * SR):int(t * SR)], F, True), F if last else 0, False))
        pieces.append(np.zeros(int(pause * SR), np.float32))
        while wi <= e:
            w = words[wi]; out.append({"w": w["w"], "start": round(w["start"] + shift, 3), "end": round(w["end"] + shift, 3)}); wi += 1
        shift += pause
        last = t
    pieces.append(fade(a[int(last * SR):], F, False))
    while wi < len(words):
        w = words[wi]; out.append({"w": w["w"], "start": round(w["start"] + shift, 3), "end": round(w["end"] + shift, 3)}); wi += 1
    full = np.concatenate(pieces).clip(-32768, 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        f.write(full.tobytes()); tmp = f.name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", tmp,
                    "-c:a", "libmp3lame", "-b:a", "192k", out_audio], check=True)
    os.unlink(tmp)
    save_json(out, out_words)
    missing = [k for k, e in enumerate(ends) if e is None]
    print(f"{len(cuts)} pauses inserted (+{shift:.1f} s), {len(full)/SR:.1f} s total; paragraphs not found: {missing}")
    return out


if __name__ == "__main__":
    main(*sys.argv[1:6])
