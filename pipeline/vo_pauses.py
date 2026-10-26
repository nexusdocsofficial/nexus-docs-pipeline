"""Add breathing room to a single-take voice-over (style guide 1b).

Inserts silence at every paragraph boundary of the script, cut at the REAL silence in the audio
(quietest 20 ms window between the two words), never at the raw timestamps:
  - after a normal paragraph:              --para  (default 0.7 s)
  - before and after a chapter announcement ("Chapter one. ..."): --chapter (default 1.8 s)
Writes the new audio and words.json on the new timeline (our format: w/start/end).

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


def quietest(a, t0, t1, win=0.02):
    """Time of the quietest window between t0 and t1 (seconds)."""
    if t1 - t0 < win * 2:
        return (t0 + t1) / 2
    i0, i1, w = int(t0 * SR), int(t1 * SR), int(win * SR)
    seg = a[i0:i1] ** 2
    if len(seg) < w:
        return (t0 + t1) / 2
    e = np.convolve(seg, np.ones(w), "valid")
    return (i0 + int(np.argmin(e)) + w // 2) / SR


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
        t = quietest(a, words[e]["end"], words[e + 1]["start"])
        cuts.append((t, pause, e))
    pieces, last, shift, out = [], 0, 0.0, []
    wi = 0
    for t, pause, e in cuts:
        pieces.append(a[int(last * SR):int(t * SR)])
        pieces.append(np.zeros(int(pause * SR), np.float32))
        while wi <= e:
            w = words[wi]; out.append({"w": w["w"], "start": round(w["start"] + shift, 3), "end": round(w["end"] + shift, 3)}); wi += 1
        shift += pause
        last = t
    pieces.append(a[int(last * SR):])
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
