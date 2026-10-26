"""Combine old + new voice-over into the long version with chapter cards and breathing pauses.
Outputs vo_long.wav and words_long.json (every word with its new start/end, source tag and chapter)."""
import json, re, subprocess

OLD = json.load(open('words.json'))
NEW = json.load(open('words_new.json'))
SRC = {'old': ('vo.mp3', OLD), 'new': ('vo_new.mp3', NEW)}
norm = lambda w: re.sub(r'[^\w]', '', w).lower()

PARA_PAUSE = 0.7       # between segments
SENT_EXTRA = 0.25      # extra breathing at existing sentence gaps inside a segment
CARD = 3.5             # chapter card length (silence under the card)
CARD_LEAD = 1.0        # extra silence before a card

PLAN = [
 ('old', 'New York. One', 'else entirely.'),
 ('card', 1, 'The Wrong Turn'),
 ('old', 'In 1609,', 'and its spices.'),
 ('new', 'His orders', 'west instead.'),
 ('old', 'He never found it.', 'money could buy.'),
 ('new', 'Hudson himself', 'not forgotten.'),
 ('old', 'So the Dutch came back.', 'to stay.'),
 ('card', 2, 'Sixty Guilders'),
 ('old', 'In 1624,', 'share the land.'),
 ('new', 'To them,', 'deal meant.'),
 ('old', 'Either way,', 'started building.'),
 ('card', 3, 'New Amsterdam'),
 ('old', 'A fort.', 'all over Europe.'),
 ('new', 'And not only Europe.', 'nobody expected.'),
 ('old', 'At the northern edge', 'right to worry.'),
 ('card', 4, 'Ships in the Harbor'),
 ('old', 'Because in 1664,', 'into the harbor.'),
 ('new', 'England and the Dutch', 'its harbor.'),
 ('old', 'The Dutch governor,', 'to give up.'),
 ('new', 'They had their homes', 'to protect.'),
 ('old', 'So he did,', 'nutmeg comes in.'),
 ('card', 5, 'The Nutmeg Island'),
 ('old', 'On the other side', 'worth a fortune.'),
 ('new', 'So valuable,', 'out of reach.'),
 ('old', 'The English had a claim', 'wanted it badly.'),
 ('new', 'Then, the Dutch found', 'peace, fast.'),
 ('old', 'In 1667,', 'second chance.'),
 ('card', 6, 'The Second Chance'),
 ('old', 'In 1673,', 'away twice.'),
 ('new', 'So, who really won', 'the deal?'),
 ('card', 7, 'Who Really Won?'),
 ('new', 'For more than a century', 'kept on growing.'),
 ('old', 'So, is anything left', 'of this kind of content.'),
]

def find(words, phrase, start=0, end_mode=False):
    ph = [norm(p) for p in phrase.replace('-', ' ').split()]
    toks = [norm(w['w']) for w in words]
    # join hyphen-split tokens like "north-" "east"
    for i in range(start, len(words)):
        j, k = i, 0
        while k < len(ph) and j < len(words):
            t = toks[j]
            if t == '' : j += 1; continue
            if t == ph[k]: j += 1; k += 1
            elif ph[k].startswith(t) and j + 1 < len(words) and t + toks[j + 1] == ph[k]: j += 2; k += 1
            else: break
        if k == len(ph):
            return (j - 1) if end_mode else i
    raise SystemExit(f'not found: {phrase}')

CHW = json.load(open('words_chapters.json'))
CH_DUR = 20.27
ANN_LEAD = 0.9      # card on screen + chime before the voice announces
ANN_TAIL = 0.9      # breathing after the announcement before the story resumes

def mid(a, b): return (a + b) / 2

import numpy as np
_PCM = {}
def pcm(f):
    if f not in _PCM:
        r = subprocess.run(['ffmpeg','-loglevel','error','-i',f,'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout
        a = np.frombuffer(r, dtype=np.float32)
        fr = 160  # 10 ms frames
        n = len(a) // fr
        _PCM[f] = 20*np.log10(np.sqrt((a[:n*fr].reshape(n, fr)**2).mean(1)) + 1e-9)
    return _PCM[f]

def quiet_point(f, lo, hi, guess):
    """middle of the longest truly silent run between lo and hi (timestamps can be off by ~0.4 s)"""
    db = pcm(f); i0, i1 = max(0, int(lo*100)), min(len(db), int(hi*100))
    if i1 <= i0: return guess
    seg = db[i0:i1]; thr = max(-50, seg.min() + 12)
    best, run = None, None
    for k, v in enumerate(seg):
        if v < thr:
            run = (run[0], k) if run else (k, k)
            if best is None or run[1]-run[0] > best[1]-best[0]: best = run
        else: run = None
    if best is None: return guess
    return (i0 + (best[0] + best[1]) / 2) / 100 + 0.005

def cut_bounds(words, i0, i1, total, f):
    s, e = words[i0]['start'], words[i1]['end']
    prev_end = words[i0 - 1]['end'] if i0 > 0 else max(0.0, s - 0.3)
    next_start = words[i1 + 1]['start'] if i1 + 1 < len(words) else min(total, e + 0.4)
    c0 = quiet_point(f, min(prev_end, s - 0.05) - 0.4, s + 0.05, max(mid(prev_end, s), s - 0.25, 0.0))
    c1 = quiet_point(f, e - 0.45, next_start + 0.05, min(mid(e, next_start), e + 0.3, total))
    if i0 == 0: c0 = max(0.0, min(c0, s))
    return max(0.0, c0), min(total, c1)

DUR = {'vo.mp3': float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','vo.mp3'],capture_output=True,text=True).stdout),
       'vo_new.mp3': float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','vo_new.mp3'],capture_output=True,text=True).stdout)}

timeline = []
out_words = []
t = 0.0
chapters = []
pos = {'old': 0, 'new': 0}
for item in PLAN:
    if item[0] == 'card':
        n = item[1]
        timeline.append(('sil', CARD_LEAD)); t += CARD_LEAD

        # find announcement word span: 'Chapter' index for chapter n
        idx = [k for k, w in enumerate(CHW) if w['w'] == 'Chapter']
        i0 = idx[n - 1]; i1 = (idx[n] - 1) if n < len(idx) else len(CHW) - 1
        c0, c1 = cut_bounds(CHW, i0, i1, CH_DUR, 'vo_chapters.mp3')
        card_start = t
        timeline.append(('sil', ANN_LEAD)); t += ANN_LEAD
        for wi in range(i0, i1 + 1):
            w = CHW[wi]
            out_words.append({'w': w['w'], 'start': round(t + w['start'] - c0, 3), 'end': round(t + w['end'] - c0, 3),
                              'src': 'chap', 'si': wi, 'chapter': n})
        timeline.append(('clip', 'vo_chapters.mp3', c0, c1)); t += c1 - c0
        timeline.append(('sil', ANN_TAIL)); t += ANN_TAIL
        chapters.append({'n': n, 'title': item[2], 'start': round(card_start, 3), 'end': round(t, 3)})
        continue
    src, a, b = item
    f, words = SRC[src]
    i0 = find(words, a, pos[src]); i1 = find(words, b, i0, end_mode=True); pos[src] = i1 + 1
    if out_words and timeline[-1][0] != 'sil':
        timeline.append(('sil', PARA_PAUSE)); t += PARA_PAUSE
    # split into chunks only at sentence ends with a real silence (>0.25 s), cut in the middle of that silence
    chunk_start = i0
    for i in range(i0, i1 + 1):
        last = i == i1
        gap = (words[i + 1]['start'] - words[i]['end']) if i + 1 < len(words) else 1
        sent_end = (not last) and words[i]['w'].rstrip()[-1:] in '.?!' and gap > 0.25
        if sent_end or last:
            c0, c1 = cut_bounds(words, chunk_start, i, DUR[f], f)
            for wi in range(chunk_start, i + 1):
                w = words[wi]
                out_words.append({'w': w['w'], 'start': round(t + w['start'] - c0, 3), 'end': round(t + w['end'] - c0, 3),
                                  'src': src, 'si': wi, 'chapter': len(chapters)})
            timeline.append(('clip', f, c0, c1)); t += c1 - c0
            if sent_end:
                extra = 0 if len(chapters) == 0 else SENT_EXTRA
                if extra: timeline.append(('sil', extra)); t += extra
            chunk_start = i + 1

# render
parts = []
inputs = []
for k, p in enumerate(timeline):
    if p[0] == 'sil':
        parts.append(f"anullsrc=r=44100:cl=mono,atrim=0:{p[1]:.3f}[s{k}]")
    else:
        inputs += ['-i', p[1]]
        idx = len(inputs) // 2 - 1
        parts.append(f"[{idx}:a]atrim={p[2]:.3f}:{p[3]:.3f},asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=mono,afade=t=in:d=0.04,afade=t=out:st={max(0, p[3]-p[2]-0.05):.3f}:d=0.05[s{k}]")
labels = ''.join(f'[s{k}]' for k in range(len(timeline)))
parts.append(f"{labels}concat=n={len(timeline)}:v=0:a=1[out]")
open('vo_filter.txt', 'w').write(';\n'.join(parts))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + inputs + ['-filter_complex_script', 'vo_filter.txt', '-map', '[out]', 'vo_long.wav'], check=True)
json.dump(out_words, open('words_long.json', 'w'))
json.dump(chapters, open('chapters.json', 'w'), indent=1)
print('total', round(t, 2), 'words', len(out_words))
for c in chapters: print(c)
json.dump(timeline, open('timeline.json','w'))
