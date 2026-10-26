"""English subtitles (SRT) from the final word timing.

usage: python3 -m pipeline.make_srt words.json out.srt
Rules: max ~40 characters per block, max 3.6 s, break on sentence ends and pauses > 0.6 s.
"""
import sys
from .common import load_words, ts


def build(words):
    cues, cur = [], []

    def text(ws):
        out = ""
        for w in ws:
            out += w["w"] if (out.endswith("-") or not out) else " " + w["w"]
        return out

    for i, w in enumerate(words):
        cur.append(w)
        t = text(cur)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 9
        end_s = w["w"][-1] in ".?!"
        comma = w["w"][-1] in ",:;"
        if (not nxt or gap > 0.6 or (end_s and len(t) > 18) or (comma and len(t) > 30) or len(t) > 40
                or cur[-1]["end"] - cur[0]["start"] > 3.6):
            end = min(w["end"] + 0.25, (nxt["start"] - 0.02) if nxt else w["end"] + 1)
            cues.append((cur[0]["start"], end, t))
            cur = []
    return cues


def write(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for k, (a, b, t) in enumerate(cues, 1):
            f.write(f"{k}\n{ts(a, srt=True)} --> {ts(b, srt=True)}\n{t}\n\n")


if __name__ == "__main__":
    words = load_words(sys.argv[1])
    cues = build(words)
    write(cues, sys.argv[2])
    print(f"{len(cues)} subtitle blocks -> {sys.argv[2]}")
