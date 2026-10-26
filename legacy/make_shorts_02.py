"""Nexus Docs Shorts builder.

Cuts segments from a finished 16:9 long video, places them on a 1080x1920
canvas (blurred background, sharp video in the middle), adds a hook title on
top, word-by-word captions below the video, and an end tag.

usage: python3 make_shorts.py [short_id ...]
"""
import json, subprocess, sys, os, re

SRC = '/mnt/user-data/uploads/Downloads/02-afrika-grenzen-final-v3.mp4'
WORDS = json.load(open('/home/claude/shorts/diar.json'))
W = [w for w in WORDS['words'] if w['type'] == 'word']
SENT = {s['id']: s for s in WORDS['sentences']}
FONTS = '/home/claude/shorts/fonts'
OUT = '/home/claude/shorts/out'
os.makedirs(OUT, exist_ok=True)

PAD_IN, PAD_OUT = 0.25, 0.55

SHORTS = {
    'A': {'file': '02-short-A-berlin-myth',
          'title': ['WHO REALLY DREW', "AFRICA'S BORDERS?"],
          # 2nd part starts on the image cut at 97.133; its audio pre-rolls and crossfades (no dip)
          'parts': [('s1', 's7', None), ('s21', 's24', 97.14)]},
    'B': {'file': '02-short-B-straight-lines',
          'title': ["WHY ARE AFRICA'S", 'BORDERS SO STRAIGHT?'],
          # start on "Why" (drops "So"), after the image cut at 126.367
          'parts': [('s27', 's31', 126.50)]},
    'C': {'file': '02-short-C-caprivi-strip',
          'title': ["GERMANY'S BORDER", 'TO NOWHERE'],
          # start just after the image cut at 162.833 (no frame of the previous shot)
          'parts': [('s32', 's41', 162.84)]},
}
XF = 0.30   # audio crossfade at joins between parts

# ---- layout (1080x1920) ----
CW, CH = 1080, 1920
VID_W = 1240                      # scale 16:9 frame to this width, crop to 1080
VID_H = round(VID_W * 9 / 16 / 2) * 2   # 698
VID_Y = 560
CAP_Y = VID_Y + VID_H + 150       # caption centre line
YELLOW = '&H001FD2FF'             # ASS BGR: #FFD21F
WHITE = '&H00FFFFFF'


def ts(t):
    t = max(0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def chunk_words(words):
    """Group words into caption chunks of max 3 words / 16 chars, breaking on punctuation."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        text = ' '.join(x['text'] for x in cur)
        if len(cur) >= 3 or len(text) >= 12 or re.search(r'[.,:;?!]$', w['text']):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def clean(t):
    return t.upper().replace('{', '').replace('}', '')


def build(sid):
    cfg = SHORTS[sid]
    # 1) segments in source time
    segs = []
    for a, b, start in cfg['parts']:
        st = start if start is not None else max(0.0, SENT[a]['start'] - PAD_IN)
        en = SENT[b]['end'] + PAD_OUT
        segs.append((st, en))
    # 2) words remapped to short time
    words, off = [], 0.0
    for st, en in segs:
        for w in W:
            if w['start'] >= st - 0.05 and w['end'] <= en:
                words.append({'text': w['text'], 'start': max(w['start'], st) - st + off, 'end': w['end'] - st + off})
        off += en - st
    total = off

    # 3) ASS file: title, captions (word highlight), end tag
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CW}
PlayResY: {CH}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Patrick Hand,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,4,0,1,3,0,8,0,0,0,1
Style: Title,Inter Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,6,3,8,60,60,0,1
Style: Cap,Inter Black,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,7,4,5,150,150,0,1
Style: Tag,Inter ExtraBold,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    # brand + title for the whole short
    ev.append(f"Dialogue: 1,{ts(0)},{ts(total)},Brand,,0,0,0,,{{\\pos({CW//2},150)\\c&H00EED322&}}NEXUS DOCS")
    t1, t2 = cfg['title']
    ev.append(f"Dialogue: 1,{ts(0)},{ts(total)},Title,,0,0,0,,{{\\pos({CW//2},250)\\fad(200,0)}}{t1}\\N{{\\c{YELLOW}}}{t2}")
    # captions
    chunks = chunk_words(words)
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0]['start'] if ci + 1 < len(chunks) else total
        ch_end = min(nxt, ch[-1]['end'] + 0.7)
        for wi, w in enumerate(ch):
            w_end = ch[wi + 1]['start'] if wi + 1 < len(ch) else ch_end
            parts = []
            for k, x in enumerate(ch):
                t = clean(x['text'])
                parts.append(f"{{\\c{YELLOW}}}{t}{{\\c{WHITE}}}" if k == wi else t)
            n_chars = len(' '.join(x['text'] for x in ch))
            base = 100 if n_chars <= 15 else int(100 * 15 / n_chars)   # keep long chunks clear of the right-side buttons
            pop = (f'{{\\fscx{int(base*1.06)}\\fscy{int(base*1.06)}\\t(0,80,\\fscx{base}\\fscy{base})}}' if wi == 0
                   else f'{{\\fscx{base}\\fscy{base}}}')
            ev.append(f"Dialogue: 2,{ts(w['start'])},{ts(w_end)},Cap,,0,0,0,,{{\\pos({CW//2},{CAP_Y})}}{pop}{' '.join(parts)}")
    # end tag: last 3 seconds
    ev.append(f"Dialogue: 3,{ts(total-3.0)},{ts(total)},Tag,,0,0,0,,{{\\pos({CW//2},{VID_Y-48})\\fad(250,0)\\c{YELLOW}}}▶  FULL STORY ON THE CHANNEL")
    ass = f'{OUT}/{cfg["file"]}.ass'
    open(ass, 'w').write(hdr + '\n'.join(ev) + '\n')

    # 4) ffmpeg: trim + concat source segments
    n = len(segs)
    fc, inputs = [], []
    for i, (st, en) in enumerate(segs):
        d = en - st
        last = i == n - 1
        # parts after the first get XF of audio pre-roll, crossfaded under the end of the previous part
        ast, ad = (st - XF, d + XF) if i > 0 else (st, d)
        inputs += ['-ss', f'{st:.3f}', '-t', f'{d:.3f}', '-i', SRC]
        inputs += ['-ss', f'{ast:.3f}', '-t', f'{ad:.3f}', '-i', SRC]
        fc.append(f"[{2*i}:v]setpts=PTS-STARTPTS[v{i}]")
        fi = 'afade=t=in:d=0.02,' if i == 0 else ''
        fo = f',afade=t=out:st={d-0.30:.3f}:d=0.30' if last else ''
        fc.append(f"[{2*i+1}:a]asetpts=PTS-STARTPTS,{fi}anull{fo}[a{i}]")
    fc.append(''.join(f'[v{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=0[vc]')
    prev = 'a0'
    for i in range(1, n):
        fc.append(f'[{prev}][a{i}]acrossfade=d={XF}:c1=tri:c2=tri[ax{i}]'); prev = f'ax{i}'
    fc.append(f'[{prev}]anull[ac]')
    fc.append('[vc]split[vbg][vfg]')
    fc.append(f'[vbg]scale=-2:{CH},crop={CW}:{CH},gblur=sigma=38,eq=brightness=-0.32:saturation=0.85[bg]')
    fc.append(f'[vfg]scale={VID_W}:{VID_H},crop={CW}:{VID_H}[fg]')
    fc.append(f'[bg][fg]overlay=0:{VID_Y},'
              f"drawbox=x=0:y={VID_Y}:w={CW}:h=4:color=0x22D3EE@0.9:t=fill,"
              f"drawbox=x=0:y={VID_Y+VID_H-4}:w={CW}:h=4:color=0x22D3EE@0.9:t=fill,"
              f"ass={ass}:fontsdir={FONTS},format=yuv420p[vout]")
    fc.append('[ac]loudnorm=I=-14:TP=-1.5:LRA=11[aout]')
    out = f'{OUT}/{cfg["file"]}.mp4'
    cmd = ['ffmpeg', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(fc),
           '-map', '[vout]', '-map', '[aout]', '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
           '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
           '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    # srt for upload (optional closed captions)
    srt = []
    for i, ch in enumerate(chunks, 1):
        nxt = chunks[i][0]['start'] if i < len(chunks) else total
        e = min(nxt, ch[-1]['end'] + 0.7)
        f = lambda t: f"{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},{int(round((t%1)*1000)):03d}"
        srt.append(f"{i}\n{f(ch[0]['start'])} --> {f(e)}\n{' '.join(x['text'] for x in ch)}\n")
    open(f'{OUT}/{cfg["file"]}.srt', 'w').write('\n'.join(srt))
    print(sid, cfg['file'], f'{total:.1f}s', len(chunks), 'caption chunks')


if __name__ == '__main__':
    for sid in (sys.argv[1:] or SHORTS.keys()):
        build(sid)
