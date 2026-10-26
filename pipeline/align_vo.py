"""Map word timestamps from the raw voice-over onto the FINAL (spliced) voice-over track.

Why: after pauses, chapter announcements or cuts are added, the raw timestamps drift.
This finds every word again in the final audio by cross-correlating the waveform, so
the shot timing never depends on manual bookkeeping.

usage: python3 -m pipeline.align_vo --source RAW.mp3 RAW_words.json [--source INSERT.mp3 INSERT_words.json ...] --final FINAL_VO --out words.json
Words that were cut from the final audio are dropped (reported).
"""
import sys, subprocess, json, os
import numpy as np
from .common import load_words, save_json

SR = 8000


def pcm(path):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def best_offset(raw, fin, t, off, back=12.0, ahead=10.0, win=(0.15, 1.35)):
    """Return (new_offset, score) for the raw window around time t."""
    a0, a1 = int((t - win[0]) * SR), int((t + win[1]) * SR)
    a0 = max(a0, 0)
    seg = raw[a0:a1]
    if len(seg) < SR * 0.3 or np.std(seg) < 1e-4:
        return off, 0.0
    lo = max(0, int((t + off - back) * SR) - (int(t * SR) - a0))
    hi = min(len(fin), int((t + off + ahead) * SR) + len(seg))
    hay = fin[lo:hi]
    if len(hay) < len(seg):
        return off, 0.0
    seg = (seg - seg.mean()) / (seg.std() + 1e-9)
    n = len(hay) + len(seg)
    nfft = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(hay, nfft) * np.conj(np.fft.rfft(seg, nfft)), nfft)[: len(hay) - len(seg) + 1]
    # local normalisation of the haystack window energy
    cs = np.concatenate([[0], np.cumsum(hay.astype(np.float64) ** 2)])
    m = np.concatenate([[0], np.cumsum(hay.astype(np.float64))])
    L = len(seg)
    e = cs[L:] - cs[:-L]
    mu = (m[L:] - m[:-L]) / L
    sd = np.sqrt(np.maximum(e / L - mu ** 2, 1e-12))
    score = c / (L * sd)
    k = int(np.argmax(score))
    pos = (lo + k) / SR                       # final time of raw sample a0
    return pos - a0 / SR, float(score[k])


def align_one(raw, fin, words, min_score=0.55, src=""):
    """Track one source through the final audio. The first confident word is found by a global search."""
    out, dropped, off, found = [], [], 0.0, False
    for i, w in enumerate(words):
        if found:
            new_off, sc = best_offset(raw, fin, w["start"], off)
        if not found or sc < min_score:
            # lost track (start, a cut, or a piece placed far away): search the whole final audio
            new_off, sc = best_offset(raw, fin, w["start"], 0.0, back=w["start"] + 1, ahead=len(fin) / SR)
        if sc >= min_score:
            off, found = new_off, True
            out.append({"w": w["w"], "start": round(w["start"] + off, 3), "end": round(w["end"] + off, 3),
                        "score": round(sc, 2), "src": src})
        else:
            dropped.append((src, i, w["w"], round(w["start"], 2), round(sc, 2)))
    return out, dropped


def align(sources, final_audio, min_score=0.55):
    """sources: list of (raw_audio, raw_words_json). Returns merged word list on the final timeline."""
    fin = pcm(final_audio)
    allw, dropped = [], []
    for k, (ra, rw) in enumerate(sources):
        o, d = align_one(pcm(ra), fin, load_words(rw), min_score, src=os.path.basename(ra))
        allw += o; dropped += d
    allw.sort(key=lambda w: w["start"])
    # the same stretch of audio can be matched from two sources (e.g. a re-recorded line): keep the best
    clean = []
    for w in allw:
        if clean and w["start"] < clean[-1]["end"] - 0.05:
            if w["score"] > clean[-1]["score"]:
                dropped.append(("overlap", clean[-1]["w"], clean[-1]["start"], clean[-1]["score"]))
                clean[-1] = w
            else:
                dropped.append(("overlap", w["w"], w["start"], w["score"]))
            continue
        clean.append(w)
    return clean, dropped


def speech_gaps(words, final_audio, min_gap=2.0):
    """Stretches where the final VO has speech but no aligned words (= unknown audio source)."""
    fin = pcm(final_audio)
    gaps = []
    edges = [(0.0, words[0]["start"])] + [(a["end"], b["start"]) for a, b in zip(words, words[1:])]
    for a, b in edges:
        if b - a < min_gap:
            continue
        seg = fin[int(a * SR):int(b * SR)]
        win = SR // 2
        loud = sum(1 for i in range(0, len(seg) - win, win) if np.sqrt(np.mean(seg[i:i + win] ** 2)) > 0.02)
        if loud * 0.5 > 1.0:
            gaps.append((round(a, 2), round(b, 2), loud * 0.5))
    return gaps


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", nargs=2, action="append", metavar=("AUDIO", "WORDS"), required=True,
                    help="raw VO audio + its transcript; repeat for every recording used in the final VO")
    ap.add_argument("--final", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    words, dropped = align(a.source, a.final)
    save_json(words, a.out)
    print(f"aligned {len(words)} words, dropped {len(dropped)}")
    gaps = speech_gaps(words, a.final)
    for g in gaps:
        print(f"  WARNING: speech without transcript {g[0]}-{g[1]} s ({g[2]:.1f} s of speech) - add its source recording")
    for d in dropped[:30]:
        print("  dropped:", d)
