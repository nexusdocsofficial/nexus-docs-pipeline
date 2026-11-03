"""Render the long video in the cloud from the same montage as the CapCut project (no Mac, no CapCut needed).

usage: python3 -m pipeline.render videos/NN/montage.json OUT.mp4 [--from N --to M]   (N/M = shot indices, for tests)

Same shots, zooms and audio stems as pipeline.montage / the CapCut draft:
  stills zoom 1.02<->1.05 (1.02<->1.035 under 3 s), alternating in/out, sub-pixel smooth (PIL affine, smoothstep);
  chapter cards 1.00->1.04; rows in montage.json "zoom" get their own centred move; the outro clip is trimmed.
Audio: VO + music + ambience + SFX + jingle stems mixed and normalised to -14 LUFS.
Run `python3 -m pipeline.montage ... images audio` first (the stems and images live in montage.json "out").
"""
import sys, os, subprocess, argparse
from PIL import Image
from .montage import M, dur_of

FPS, W, H = 30, 1920, 1080


def ease(t):
    return t * t * (3 - 2 * t)


def still(src, out, dur, z0, z1):
    img = Image.open(src).convert('RGB'); sw, sh = img.size
    s0 = max(W / sw, H / sh); frames = max(1, round(dur * FPS))
    ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-tune', 'animation',
                           '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for i in range(frames):
        z = z0 + (z1 - z0) * ease(i / max(1, frames - 1))
        a = 1 / (s0 * z); hw, hh = W / 2 * a, H / 2 * a
        cx, cy = sw / 2, sh / 2
        fr = img.transform((W, H), Image.AFFINE, (a, 0, cx - hw, 0, a, cy - hh), resample=Image.BICUBIC)
        ff.stdin.write(fr.tobytes())
    ff.stdin.close(); ff.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cfg'); ap.add_argument('out')
    ap.add_argument('--from', dest='a', type=int, default=0); ap.add_argument('--to', dest='b', type=int, default=None)
    x = ap.parse_args()
    m = M(x.cfg); c = m.cfg; od = m.out
    rd = os.path.join(od, 'render'); os.makedirs(rd, exist_ok=True)
    clips, k = [], 0
    for idx, s in enumerate(m.shots):
        dur = s['end'] - s['start']
        o = os.path.join(rd, f'c{idx:03d}.mp4'); clips.append(o)
        if s['kind'] == 'still' and s['n'] not in c.get('zoom', {}):
            z = (1.02, 1.05) if dur >= 3 else (1.02, 1.035)
            z = z if k % 2 == 0 else z[::-1]; k += 1
        if idx < x.a or (x.b is not None and idx > x.b) or os.path.exists(o):
            continue
        src = os.path.join(od, s['src'])
        if s['kind'] == 'outro':
            sd = dur_of(src)
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, '-an', '-vf',
                            f'scale={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={max(0, dur - sd) + 0.2:.3f},'
                            f'trim=0:{dur:.3f},fade=t=out:st={dur - 1.0:.3f}:d=1.0,format=yuv420p',
                            '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', o], check=True)
        elif s['kind'] == 'card':
            still(src, o, dur, 1.0, 1.04)
        elif s['n'] in c.get('zoom', {}):
            zz = c['zoom'][s['n']]; still(src, o, dur, zz[0], zz[1])
        else:
            still(src, o, dur, *z)
        print(idx, s['n'], flush=True)
    if x.b is not None or x.a:
        return
    lst = os.path.join(rd, 'list.txt')
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in clips))
    vt = os.path.join(rd, 'video_track.mp4')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vt], check=True)
    st = [os.path.join(od, f) for f in ('vo.m4a', 'music.m4a', 'ambience.m4a', 'sfx.m4a', 'jingle.m4a')]
    ins = sum([['-i', p] for p in st], [])
    n = len(st)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', vt, *ins, '-filter_complex',
                    ''.join(f'[{i + 1}]aresample=48000,aformat=channel_layouts=stereo[a{i}];' for i in range(n)) +
                    ''.join(f'[a{i}]' for i in range(n)) +
                    f'amix=inputs={n}:normalize=0:duration=first,atrim=0:{m.total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                    '-movflags', '+faststart', x.out], check=True)
    print('ok', x.out)


if __name__ == '__main__':
    main()
