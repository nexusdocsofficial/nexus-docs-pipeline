"""Montage lange versie video 3: sub-pixel zooms, hoofdstukkaarten, muziek per hoofdstuk, sfeergeluid, SFX en outro.
Gebruik: python3 render_long.py video   (beelden)  |  python3 render_long.py audio  |  python3 render_long.py mux"""
import json, subprocess, os, sys
from PIL import Image

HERE = '/home/claude/nexus/03-newyork'
UP = '/mnt/user-data/uploads/flow-mcp-out/'
OUT = f'{HERE}/render_long'
LIB = '/home/claude/nexus/library'
os.makedirs(OUT, exist_ok=True)
shots = json.load(open(f'{HERE}/shotlist_long.json'))
oldmap = json.load(open(f'{HERE}/shotmap.json'))
newmap = json.load(open(f'{HERE}/newmap.json')) if os.path.exists(f'{HERE}/newmap.json') else {}
CH = json.load(open(f'{HERE}/chapters.json'))
FPS, W, H = 30, 1920, 1080
OUTRO_LEN = 8.0
shots[-1]['end'] = round(shots[-1]['start'] + OUTRO_LEN, 3); shots[-1]['dur'] = OUTRO_LEN
TOTAL = shots[-1]['end']
V2 = json.load(open(f'{HERE}/v2map.json')) if os.path.exists(f'{HERE}/v2map.json') else {}
# v3: chapter-5 card and the next map share one framing and dissolve into each other
FOCUS = json.load(open(f'{HERE}/cards/focus.json'))
RUNPIN = tuple(FOCUS['5'][0])
SPECIAL = {69: dict(zr=(1.0, 1.07), anchor=RUNPIN),
           70: dict(zr=(1.07, 1.10), anchor=RUNPIN, blend=(f'{HERE}/cards/card-5.jpg', 1.2))}
OUTRO = UP + '02-Afrika-grenzen/scene-201.mp4'

def src_for(s):
    if os.path.exists(f"{HERE}/fixed/shot{s['n']}.jpg"):
        return f"{HERE}/fixed/shot{s['n']}.jpg"
    if str(s['n']) in V2:
        return UP + V2[str(s['n'])] + '.jpeg'
    if s['kind'] == 'card':
        return f"{HERE}/cards/card-{s['card']}.jpg"
    if s['kind'] == 'old' or s['type'] == 'reuse':
        v = oldmap[str(s['old'])]
        return UP + '03-New-York/' + v + '.jpeg'
    return UP + newmap[str(s['n'])] + '.jpeg'

def ease(t): return t * t * (3 - 2 * t)
PAT = ['in', 'out', 'in', 'in_left', 'out', 'in_right']

def still(src, out, dur, n, Z, focus=None, zr=None, blend=None, anchor=None):
    img = Image.open(src).convert('RGB'); sw, sh = img.size
    if blend:   # (image path, seconds): dissolve in from that image (same size, same framing)
        bimg = Image.open(blend[0]).convert('RGB').resize((sw, sh))
    s0 = max(W / sw, H / sh); frames = max(1, round(dur * FPS)); p = PAT[n % len(PAT)]
    ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-tune', 'animation',
                           '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for i in range(frames):
        t = ease(i / max(1, frames - 1))
        z = 1 + Z * t if p.startswith('in') else 1 + Z * (1 - t)
        if zr: z = zr[0] + (zr[1] - zr[0]) * t; p = 'in'
        a = 1 / (s0 * z); hw, hh = W / 2 * a, H / 2 * a
        bias = {'in_left': 0.4, 'in_right': 0.6}.get(p, 0.5)
        cx = hw + (sw - 2 * hw) * bias; cy = sh / 2
        if focus:   # drift toward the map pin
            fx, fy = focus[0] * sw / W, focus[1] * sh / H
            cx = min(max(sw / 2 + (fx - sw / 2) * t * 0.9, hw), sw - hw)
            cy = min(max(sh / 2 + (fy - sh / 2) * t * 0.9, hh), sh - hh)
        if anchor:   # zoom steadily into one fixed spot (the spot stays put on screen)
            px, py = anchor; fx, fy = px / s0, py / s0
            M = (a, 0, fx - px * a, 0, a, fy - py * a)
        else:
            M = (a, 0, cx - hw, 0, a, cy - hh)
        fr = img.transform((W, H), Image.AFFINE, M, resample=Image.BICUBIC)
        if blend and i < blend[1] * FPS:
            k = ease(i / (blend[1] * FPS))
            fb = bimg.transform((W, H), Image.AFFINE, M, resample=Image.BICUBIC)
            fr = Image.blend(fb, fr, k)
        ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait()

def video(only=None):
    clips = []
    for s in shots:
        out = f"{OUT}/c{s['n']:03d}.mp4"; clips.append(out)
        if only and s['n'] not in only: continue
        if os.path.exists(out) and '--force' not in sys.argv and not only: continue
        if s['kind'] == 'outro':
            d = s['dur']
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', OUTRO, '-t', f'{d:.3f}', '-an', '-vf',
                            f'trim=0:6.4,setpts=PTS-STARTPTS,scale={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={d-6.4+0.1:.3f},trim=0:{d:.3f},fade=t=out:st={d-1.0:.3f}:d=1.0,format=yuv420p',
                            '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', out], check=True)
        else:
            if s['n'] in SPECIAL:
                still(src_for(s), out, s['dur'], s['n'], 0, **SPECIAL[s['n']])
            elif s['kind'] == 'card':
                pts = FOCUS[str(s['card'])]
                fc = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
                still(src_for(s), out, s['dur'], s['n'], 0, zr=(1.0, 1.07 if len(pts) == 1 else 1.04), anchor=fc)
            else:
                Z = 0.03 if s['dur'] >= 3 else 0.015
                still(src_for(s), out, s['dur'], s['n'], Z)
        print(s['n'], flush=True)
    with open(f'{OUT}/list.txt', 'w') as f:
        for c in clips: f.write(f"file '{c}'\n")
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{OUT}/list.txt', '-c', 'copy',
                    f'{OUT}/video_track.mp4'], check=True)

# ---------- audio v2: music follows the story beats, ambience only briefly at scene starts ----------
S_BY_N = {s['n']: s for s in shots}
CARD_N = {s['n'] for s in shots if s['kind'] == 'card'}
OUTRO_T = shots[-1]['start']
JINGLE = f'{LIB}/muziek/outro-jingle.mp3'
# (first shot of the beat, track, offset in track (s), gain dB)
MUSIC_CUES = [
    (1, '06-intrigue', 6, -21),            # hook: curiosity, keeps people watching
    (8, '07-expedition', 0, -23),          # ch1: Hudson's mission, ice, mutiny
    (25, '06-intrigue', 30, -23),          # ch2: the myth of the 24 dollars
    (39, '03-hidden-story', 0, -25),       # ch3: the busy trading town (softer)
    (45, '04-rising-tension', 10, -23),    # Stuyvesant arrives: order, clash
    (57, '08-conflict', 0, -23),           # ch4: English warships
    (69, '04-rising-tension', 40, -23),    # ch5: the nutmeg island
    (74, '09-dark-waters', 5, -23),        # Banda 1621
    (81, '08-conflict', 40, -23),          # raid on the Medway
    (86, '03-hidden-story', 40, -25),      # peace of Breda
    (91, '08-conflict', 65, -23),          # ch6: 1673 attack
    (101, '10-turning-tide', 0, -24),      # handed back, twice -> who really won (runs through card 7)
    (115, '01-curious-beginnings', 5, -25),  # walk through today's New York
]
AMB_CUES = [(9, 'haven-1600', 7), (16, 'bos-rivier', 7), (26, 'bos-rivier', 6), (40, 'stad-1600', 7),
            (58, 'haven-1600', 6), (72, 'tropisch-eiland', 7), (93, 'haven-1600', 6), (116, 'stad-modern', 7)]

def dur_of(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout)

def piece(src, offset, length, gain, fin, fout, out, norm=-20):
    avail = dur_of(src) - 8          # tracks fade out at the end; never use the tail
    offset = max(0, min(offset, avail - length))
    loop = ['-stream_loop', '-1'] if offset + length > avail else []
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + loop + ['-ss', f'{offset:.3f}', '-i', src, '-t', f'{length:.3f}',
                    '-af', f'loudnorm=I={norm}:TP=-2,volume={gain}dB,afade=t=in:d={fin}:curve=qsin,'
                           f'afade=t=out:st={max(0, length - fout):.3f}:d={fout}:curve=qsin,aresample=48000',
                    '-ac', '2', out], check=True)

def place(parts, out):
    """parts: (start_time, file). Mix them on one timeline of TOTAL seconds."""
    ins, f = [], []
    for k, (a, p) in enumerate(parts):
        ins += ['-i', p]; ms = int(a * 1000)
        f.append(f"[{k}]adelay={ms}|{ms}[l{k}]")
    f.append(''.join(f'[l{k}]' for k in range(len(parts))) +
             f"amix=inputs={len(parts)}:normalize=0:duration=longest,apad,atrim=0:{TOTAL:.3f}[o]")
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + ins + ['-filter_complex', ';'.join(f), '-map', '[o]',
                    '-ar', '48000', '-ac', '2', out], check=True)

def audio():
    # music: one piece per story beat; cross-fades sit in the pauses (cards: during the card)
    def edge(n):
        card = n in CARD_N
        return S_BY_N[n]['start'] - (1.5 if card else 3.0), (5.0 if card else 6.0)
    parts = []
    for k, (n, trk, off, g) in enumerate(MUSIC_CUES):
        a, fin = edge(n) if n != 1 else (0.0, 0.5)
        if k + 1 < len(MUSIC_CUES):
            b0, fout = edge(MUSIC_CUES[k + 1][0]); b = b0 + fout
        else:
            b, fout = OUTRO_T + 0.4, 3.5          # music ends with the story; the outro gets its own jingle
        p = f'{OUT}/mu{k:02d}.wav'
        piece(f'{LIB}/muziek/{trk}.mp3', off, b - a, g, fin, fout, p)
        parts.append((a, p))
    place(parts, f'{OUT}/music_track.wav')

    # ambience: a few seconds to set the scene, then it fades away
    parts = []
    for k, (n, nm, d) in enumerate(AMB_CUES):
        a = max(0, S_BY_N[n]['start'] - 0.3); p = f'{OUT}/am{k:02d}.wav'
        piece(f'{LIB}/sfeer/{nm}.mp3', 0, d, -24, 1.0, 3.5, p)
        parts.append((a, p))
    place(parts, f'{OUT}/amb_track.wav')

    # SFX: a clear chime on every chapter card, and three big moments
    parts = []
    for n in (58, 83, 109):
        parts.append((max(0, S_BY_N[n]['start'] - 0.15), '/home/claude/nexus/02-afrika/sfx/whoosh_low.wav', -10))
    files = []
    for k, (a, p, g) in enumerate(parts):
        o = f'{OUT}/sx{k:02d}.wav'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', p, '-af', f'volume={g}dB,aresample=48000', '-ac', '2', o], check=True)
        files.append((a, o))
    place(files, f'{OUT}/sfx_track.wav')

    # outro jingle
    piece(JINGLE, 0, min(OUTRO_LEN, dur_of(JINGLE)), -15, 0.05, 0.6, f'{OUT}/jg.wav')
    place([(OUTRO_T, f'{OUT}/jg.wav')], f'{OUT}/jingle_track.wav')
    print('audio ok')

def mux():
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', f'{OUT}/video_track.mp4', '-i', f'{HERE}/vo_long.wav',
                    '-i', f'{OUT}/music_track.wav', '-i', f'{OUT}/amb_track.wav', '-i', f'{OUT}/sfx_track.wav', '-i', f'{OUT}/jingle_track.wav',
                    '-filter_complex',
                    f"[1]aresample=48000,aformat=channel_layouts=stereo,apad[vo];[2]volume=1[mu];[3]volume=1[am];[4]volume=1[sf];[5]volume=1[jg];"
                    f"[vo][mu][am][sf][jg]amix=inputs=5:normalize=0:duration=first,atrim=0:{TOTAL:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                    f'{HERE}/03-new-york-final.mp4'], check=True)
    print('mux ok')

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'video':
        only = {int(x) for x in sys.argv[2].split(',')} if len(sys.argv) > 2 and sys.argv[2][0].isdigit() else None
        video(only)
    elif cmd == 'audio': audio()
    elif cmd == 'mux': mux()
