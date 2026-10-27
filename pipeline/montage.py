"""Full montage for a long video from one config: images, chapter cards, audio stems and the CapCut draft.

usage: python3 -m pipeline.montage videos/NN/montage.json [images|audio|draft|all]

montage.json
  name        CapCut project name (an existing empty project, e.g. "05", is reused: pass ids)
  ids         {timeline, project, meta} of that empty project (see build_capcut.build)
  img_root    local folder with the Flow images (staged from the Mac)
  files       beeld-bestanden.json (row n -> file relative to img_root)
  prompts     prompts.json (start/end per row), words  words.json
  vo, lib, outro, outro_len, out (local build folder), mac_dir (where the media will live on the Mac)
  chapters    [{n, row, title}]
  music       [[row, track, offset_s, gain_db_vs_voice]]   one cue per story beat. On a chapter card the old music has
              faded out before the card and the new piece starts with it; within a chapter a soft cross-fade of
              music_crossfade s (default 8) ends exactly on the new beat
  zoom        {row: [z0, z1]}                              special camera move, centred (an anchored move can show black edges)
  vo_fix      [[t0, t1, gain]]                             soften a click/glitch in the voice-over
  Rows that map to the same image file as the row before become one longer shot.
  ambience    [[row, file_in_lib_sfeer, seconds]]          short scene-setting beds, then fade
  whoosh      {src, rows: [...]}                           a few big moments only
Writes: out/img-NNN.jpg, out/card-N.jpg, out/{vo,music,ambience,sfx,jingle}.m4a, out/outro.mp4, out/draft/,
        videos/NN/shots.json and chapters.json (for qa_check, describe, upload_folder).
"""
import sys, os, json, subprocess, shutil
from PIL import Image
from .common import load_json, save_json
from .chapter_cards import card as make_card, fit16x9
from . import build_capcut

VO_LUFS = -14.5


def sh(*a):
    subprocess.run(list(a), check=True)


def dur_of(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout)


def lufs(p, ss=0, t=None):
    a = ['ffmpeg', '-hide_banner', '-ss', str(ss)] + (['-t', str(t)] if t else []) + ['-i', p, '-af', 'ebur128', '-f', 'null', '-']
    err = subprocess.run(a, capture_output=True, text=True).stderr
    line = [l for l in err.splitlines() if l.strip().startswith('I:')][-1]
    return float(line.split()[1])


class M:
    def __init__(self, cfg_path):
        self.cfg = c = load_json(cfg_path)
        self.vdir = os.path.dirname(cfg_path)
        rel = lambda p: p if os.path.isabs(p) else os.path.join(self.vdir, p)
        self.files = load_json(rel(c['files']))
        self.prompts = {p['n']: p for p in load_json(rel(c['prompts']))}
        self.out = c['out']; os.makedirs(self.out, exist_ok=True)
        rows = [p for p in load_json(rel(c['prompts']))]
        self.order = [p['n'] for p in rows]
        self.cards = {ch['row']: ch for ch in c['chapters']}
        self.outro_t = rows[-1]['end']           # VO line of the outro starts here
        self.total = self.outro_t + c['outro_len']
        self.shots, si = [], 0
        self.row_start = {}
        for k, n in enumerate(self.order):
            st = 0.0 if k == 0 else self.prompts[n]['start']
            e = self.prompts[self.order[k + 1]]['start'] if k + 1 < len(self.order) else self.outro_t
            self.row_start[n] = st
            kind = 'card' if n in self.cards else 'still'
            prev = self.shots[-1] if self.shots else None
            if kind == 'still' and prev and prev['kind'] == 'still' and self.files[n] == self.files[prev['n']]:
                prev['end'] = round(e, 3); prev['rows'].append(n)      # same image as the row before: one longer shot
                if n.isdigit():
                    si += 1
                continue
            # img-NNN = 0-based index among the numbered stills (qa_check maps it back to the beeldenlijst);
            # extra rows inserted later (e.g. "23m") get extra-<n>.jpg
            if kind == 'card':
                src = f'card-{self.cards[n]["n"]}.jpg'
            elif n.isdigit():
                src = f'img-{si:03d}.jpg'; si += 1
            else:
                src = f'extra-{n}.jpg'
            self.shots.append({'n': n, 'rows': [n], 'start': round(st, 3), 'end': round(e, 3), 'kind': kind, 'src': src})
        self.shots.append({'n': 'O', 'rows': ['O'], 'start': round(self.outro_t, 3), 'end': round(self.total, 3), 'kind': 'outro',
                           'src': 'outro.mp4'})
        self.row_start['O'] = self.outro_t
        self.by_n = {s['n']: s for s in self.shots}

    # ---------------- images ----------------
    def images(self):
        c = self.cfg
        for s in self.shots:
            o = os.path.join(self.out, s['src'])
            if s['kind'] == 'outro':
                shutil.copy(c['outro'], o); continue
            src = os.path.join(c['img_root'], self.files[s['n']])
            if s['kind'] == 'card':
                ch = self.cards[s['n']]; make_card(src, o, ch['n'], ch['title'])
            else:
                fit16x9(Image.open(src)).save(o, quality=92)
        save_json([{k: v for k, v in s.items()} | {'src': os.path.join(c['mac_dir'], s['src'])} for s in self.shots],
                  os.path.join(self.vdir, 'shots.json'))
        save_json([{'n': ch['n'], 'title': ch['title'], 'start': self.by_n[ch['row']]['start']} for ch in c['chapters']],
                  os.path.join(self.vdir, 'chapters.json'))
        print(f'{len(self.shots)} shots, {self.total:.1f} s')

    # ---------------- audio ----------------
    def _piece(self, src, offset, length, level, fin, fout, out):
        avail = max(1.0, dur_of(src) - 8)            # library tracks fade out at the end; never use the tail
        offset = max(0, min(offset, avail - length)) if length < avail else 0
        loop = ['-stream_loop', '-1'] if offset + length > avail else []
        gain = level - self._lufs(src)
        sh('ffmpeg', '-loglevel', 'error', '-y', *loop, '-ss', f'{offset:.3f}', '-i', src, '-t', f'{length:.3f}', '-af',
           f'volume={gain:.2f}dB,afade=t=in:d={fin}:curve=qsin,afade=t=out:st={max(0, length - fout):.3f}:d={fout}:curve=qsin,'
           f'aresample=48000', '-ac', '2', out)

    _lc = {}

    def _lufs(self, p):
        if p not in self._lc:
            self._lc[p] = lufs(p)
        return self._lc[p]

    def _place(self, parts, out):
        if not parts:
            sh('ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f'{self.total:.3f}',
               '-c:a', 'aac', '-b:a', '192k', out); return
        ins, f = [], []
        for k, (a, p) in enumerate(parts):
            ins += ['-i', p]; ms = int(a * 1000)
            f.append(f'[{k}]adelay={ms}|{ms}[l{k}]')
        f.append(''.join(f'[l{k}]' for k in range(len(parts))) +
                 f'amix=inputs={len(parts)}:normalize=0:duration=longest,apad,atrim=0:{self.total:.3f}[o]')
        sh('ffmpeg', '-loglevel', 'error', '-y', *ins, '-filter_complex', ';'.join(f), '-map', '[o]', '-ar', '48000', '-ac', '2',
           '-c:a', 'aac', '-b:a', '192k', out)

    def audio(self):
        c, tmp = self.cfg, os.path.join(self.out, 'tmp'); os.makedirs(tmp, exist_ok=True)
        # voice-over at a fixed loudness
        g = VO_LUFS - lufs(c['vo'])
        vo_src = c['vo']
        if c.get('vo_fix'):                       # [[t0, t1, gain]]: soften a glitch/click in the VO (8 ms ramps)
            import numpy as np, wave
            raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', c['vo'], '-ac', '1', '-ar', '48000', '-f', 's16le', '-'],
                                 capture_output=True, check=True).stdout
            x = np.frombuffer(raw, np.int16).astype(np.float32)
            env = np.ones_like(x); r = int(0.008 * 48000)
            for t0, t1, gn in c['vo_fix']:
                i0, i1 = int(t0 * 48000), int(t1 * 48000)
                env[i0:i1] = np.minimum(env[i0:i1], gn)
                env[i0 - r:i0] = np.minimum(env[i0 - r:i0], np.linspace(1, gn, r))
                env[i1:i1 + r] = np.minimum(env[i1:i1 + r], np.linspace(gn, 1, r))
            vo_src = os.path.join(tmp, 'vo-fixed.wav')
            with wave.open(vo_src, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
                w.writeframes((x * env).clip(-32768, 32767).astype(np.int16).tobytes())
        sh('ffmpeg', '-loglevel', 'error', '-y', '-i', vo_src, '-af', f'volume={g:.2f}dB,aresample=48000,apad',
           '-t', f'{self.total:.3f}', '-ac', '2', '-c:a', 'aac', '-b:a', '192k', os.path.join(self.out, 'vo.m4a'))

        cards = {ch['row'] for ch in c['chapters']}
        XF = c.get('music_crossfade', 8.0)
        parts, cues = [], c['music']
        for k, (n, trk, off, gdb) in enumerate(cues):
            t = self.row_start[n]
            if k == 0:
                a, fin = 0.0, 0.5
            elif n in cards:             # new chapter: the old music is gone before the card, the new one starts with it
                a, fin = t - 0.2, 1.5
            else:                        # within a chapter: long, soft cross-fade that ends on the new beat
                a, fin = t - XF, XF
            if k + 1 < len(cues):
                n2 = cues[k + 1][0]; t2 = self.row_start[n2]
                if n2 in cards:
                    b, fout = t2 + 0.2, 3.5
                else:
                    b, fout = t2, XF
            else:
                b, fout = self.outro_t + 0.4, 3.5
            a = max(0.0, a)
            p = os.path.join(tmp, f'mu{k:02d}.wav')
            self._piece(os.path.join(c['lib'], 'muziek', trk + '.mp3'), off, b - a, VO_LUFS + gdb, fin, fout, p)
            parts.append((a, p))
        self._place(parts, os.path.join(self.out, 'music.m4a'))

        parts = []
        for k, (n, nm, d) in enumerate(c.get('ambience', [])):
            a = max(0, self.row_start[n] - 0.3); p = os.path.join(tmp, f'am{k:02d}.wav')
            self._piece(os.path.join(c['lib'], 'sfeer', nm + '.mp3'), 0, d, VO_LUFS - 26, 1.0, 3.5, p)
            parts.append((a, p))
        self._place(parts, os.path.join(self.out, 'ambience.m4a'))

        w = c.get('whoosh') or {}
        self._place([(max(0, self.row_start[n] - 0.15), w['src']) for n in w.get('rows', [])],
                    os.path.join(self.out, 'sfx.m4a'))

        p = os.path.join(tmp, 'jingle.wav')
        jg = os.path.join(c['lib'], 'muziek', 'outro-jingle.mp3')
        self._piece(jg, 0, min(c['outro_len'], dur_of(jg)), VO_LUFS - 12, 0.05, 0.6, p)
        self._place([(self.outro_t, p)], os.path.join(self.out, 'jingle.m4a'))
        print('audio ok')

    # ---------------- CapCut draft ----------------
    def draft(self):
        c, md = self.cfg, self.cfg['mac_dir']
        shots, k = [], 0
        for s in self.shots:
            dur = s['end'] - s['start']
            if s['kind'] == 'outro':
                shots.append({'path': f"{md}/{s['src']}", 'w': 1920, 'h': 1080, 'start': s['start'], 'dur': dur,
                              'zoom': (1.0, 1.0), 'src_dur': dur_of(os.path.join(self.out, s['src']))})
            elif s['kind'] == 'card':
                shots.append({'path': f"{md}/{s['src']}", 'w': 1920, 'h': 1080, 'start': s['start'], 'dur': dur, 'zoom': (1.0, 1.04)})
            elif s['n'] in c.get('zoom', {}):          # special move, e.g. a long zoom-out over a whole route
                zz = c['zoom'][s['n']]            # [z0, z1] centred, or [z0, z1, ax, ay] anchored (risk of black edges)
                shots.append({'path': f"{md}/{s['src']}", 'w': 1920, 'h': 1080, 'start': s['start'], 'dur': dur,
                              'zoom': (zz[0], zz[1]), 'anchor': (zz[2], zz[3]) if len(zz) == 4 else None})
            else:
                z = (1.02, 1.05) if dur >= 3 else (1.02, 1.035)
                shots.append({'path': f"{md}/{s['src']}", 'w': 1920, 'h': 1080, 'start': s['start'], 'dur': dur,
                              'zoom': z if k % 2 == 0 else z[::-1]})
                k += 1
        stems = []
        for nm, f, vol in [('Voice-over', 'vo.m4a', 1.0), ('Music', 'music.m4a', 1.0), ('Ambience', 'ambience.m4a', 1.0),
                           ('SFX', 'sfx.m4a', 1.0), ('Outro jingle', 'jingle.m4a', 1.0)]:
            stems.append({'name': nm, 'path': f'{md}/{f}', 'dur': dur_of(os.path.join(self.out, f)), 'volume': vol})
        dd = os.path.join(self.out, 'draft')
        shutil.rmtree(dd, ignore_errors=True); os.makedirs(dd)
        entry = build_capcut.build(c['name'], shots, stems, dd, c.get('ids'))
        save_json(entry, os.path.join(dd, 'root_entry.json'))
        print('draft ok ->', dd)


if __name__ == '__main__':
    m = M(sys.argv[1]); what = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if what in ('images', 'all'): m.images()
    if what in ('audio', 'all'): m.audio()
    if what in ('draft', 'all'): m.draft()
