"""Build a CapCut 9.6 (Mac) draft from a Nexus Docs shot list.

Uses a real CapCut draft (template_draft_info.json) as the schema source, then fills:
  video track 1 : stills with zoom keyframes (and anchored zoom for chapter cards)
  audio tracks  : voice-over, music, ambience, sfx (each a separate stem, so volumes can be changed in CapCut)

usage (from python): build(name, shots, stems, mac_media_dir, out_dir)
  shots : list of dicts {path (Mac path), w, h, start, dur, zoom: (z0, z1), anchor: (px, py) or None}
  stems : list of dicts {name, path (Mac path), dur, volume}
"""
import json, copy, uuid, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = json.load(open(f'{HERE}/template_draft_info.json'))
TPL_META = json.load(open(f'{HERE}/template_meta.json'))
ROOT = '/Users/USER/Movies/CapCut/User Data/Projects/com.lveditor.draft'
US = 1_000_000
W, H = 1920, 1080

def U(): return str(uuid.uuid4()).upper()
def u(): return str(uuid.uuid4())
def us(t): return int(round(t * US))

M = TPL['materials']
T_VID = M['videos'][0]
T_AUD = next(a for a in M['audios'] if a['type'] == 'extract_music')
T_VSEG = TPL['tracks'][0]['segments'][0]
T_ASEG = next(t for t in TPL['tracks'] if t['type'] == 'audio')['segments'][0]
T_TRACK = {k: v for k, v in TPL['tracks'][0].items() if k != 'segments'}
AUX = {k: M[k][0] for k in ['speeds', 'placeholder_infos', 'canvases', 'material_animations',
                            'sound_channel_mappings', 'material_colors', 'loudnesses', 'vocal_separations']}

def aux(mats, kind):
    x = copy.deepcopy(AUX[kind]); x['id'] = U(); mats[kind].append(x); return x['id']

def kf(prop, pts):
    return {'id': U(), 'material_id': '', 'property_type': prop,
            'keyframe_list': [{'id': U(), 'curveType': 'Line', 'time_offset': int(t), 'left_control': {'x': 0.0, 'y': 0.0},
                               'right_control': {'x': 0.0, 'y': 0.0}, 'values': [float(v)], 'string_value': '', 'graphID': ''}
                              for t, v in pts]}

def build(name, shots, stems, out_dir):
    d = copy.deepcopy(TPL)
    did = U()
    d['id'] = did; d['name'] = name
    mats = d['materials']
    for k in mats:
        if isinstance(mats[k], list): mats[k] = []
    d['keyframes'] = {k: [] for k in d['keyframes']}
    tracks = []
    meta_items = []
    now = int(time.time())

    # ---- video track ----
    vt = copy.deepcopy(T_TRACK); vt['id'] = U(); vt['segments'] = []
    for i, s in enumerate(shots):
        m = copy.deepcopy(T_VID); m['id'] = u(); m['unique_id'] = uuid.uuid4().hex
        m['path'] = s['path']; m['material_name'] = os.path.basename(s['path'])
        m['width'], m['height'] = s['w'], s['h']; m['duration'] = 10_800_000_000; m['type'] = 'photo'
        mats['videos'].append(m)
        refs = [aux(mats, k) for k in ['speeds', 'placeholder_infos', 'canvases', 'material_animations',
                                       'sound_channel_mappings', 'material_colors', 'loudnesses', 'vocal_separations']]
        seg = copy.deepcopy(T_VSEG); seg['id'] = U(); seg['material_id'] = m['id']; seg['extra_material_refs'] = refs
        dur = us(s['dur'])
        seg['source_timerange'] = {'start': 0, 'duration': dur}
        seg['target_timerange'] = {'start': us(s['start']), 'duration': dur}
        z0, z1 = s['zoom']
        seg['clip'] = {'scale': {'x': z0, 'y': z0}, 'rotation': 0.0, 'transform': {'x': 0.0, 'y': 0.0},
                       'flip': {'vertical': False, 'horizontal': False}, 'alpha': 1.0}
        seg['uniform_scale'] = {'on': True, 'value': z0}
        # zoom steps: ease in/out approximated with 5 keyframes on a smoothstep curve
        steps = [0, 0.25, 0.5, 0.75, 1.0]
        ease = lambda t: t * t * (3 - 2 * t)
        zs = [(dur * t, z0 + (z1 - z0) * ease(t)) for t in steps]
        kfs = [kf('KFTypeScaleX', zs), kf('KFTypeScaleY', zs)]
        if s.get('anchor'):
            # keep the anchor point fixed on screen while scaling around the centre
            px, py = s['anchor']
            def pos(z):
                return ((W / 2 - px) * (z - 1) / (W / 2), -(H / 2 - py) * (z - 1) / (H / 2))
            kfs.append(kf('KFTypePositionX', [(t, pos(z)[0]) for t, z in zs]))
            kfs.append(kf('KFTypePositionY', [(t, pos(z)[1]) for t, z in zs]))
            px0, py0 = pos(z0); seg['clip']['transform'] = {'x': px0, 'y': py0}
        seg['common_keyframes'] = kfs
        seg['render_index'] = 0; seg['track_render_index'] = 0
        vt['segments'].append(seg)
        meta_items.append({'file_Path': s['path'], 'metetype': 'photo', 'width': s['w'], 'height': s['h'], 'duration': 5_000_000})
    tracks.append(vt)

    # ---- audio tracks, one per stem ----
    for k, st in enumerate(stems):
        m = copy.deepcopy(T_AUD); m['id'] = u(); m['unique_id'] = uuid.uuid4().hex
        m['path'] = st['path']; m['name'] = os.path.basename(st['path']); m['duration'] = us(st['dur'])
        mats['audios'].append(m)
        refs = [aux(mats, x) for x in ['speeds', 'placeholder_infos', 'sound_channel_mappings', 'vocal_separations']]
        seg = copy.deepcopy(T_ASEG); seg['id'] = U(); seg['material_id'] = m['id']; seg['extra_material_refs'] = refs
        seg['source_timerange'] = {'start': 0, 'duration': us(st['dur'])}
        seg['target_timerange'] = {'start': 0, 'duration': us(st['dur'])}
        seg['volume'] = st.get('volume', 1.0); seg['last_nonzero_volume'] = 1.0
        seg['track_render_index'] = k + 1; seg['common_keyframes'] = []
        at = copy.deepcopy(T_TRACK); at['id'] = U(); at['type'] = 'audio'; at['name'] = st['name']; at['is_default_name'] = False
        at['segments'] = [seg]
        tracks.append(at)
        meta_items.append({'file_Path': st['path'], 'metetype': 'music', 'width': 0, 'height': 0, 'duration': us(st['dur'])})

    d['tracks'] = tracks
    d['duration'] = max(us(shots[-1]['start'] + shots[-1]['dur']), max(us(s['dur']) for s in stems))

    # ---- write folder ----
    fold = f'{ROOT}/{name}'
    os.makedirs(f'{out_dir}/Timelines/{did}', exist_ok=True)
    js = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
    for p in [f'{out_dir}/draft_info.json', f'{out_dir}/Timelines/{did}/draft_info.json']:
        open(p, 'w', encoding='utf-8').write(js)
    tnow = int(time.time() * 1e6)
    json.dump({'config': {'color_space': -1, 'hdr_vivid': False, 'mixed_track_mode_on': False, 'render_index_track_mode_on': True,
                          'use_float_render': False}, 'create_time': tnow, 'id': did, 'main_timeline_id': did,
               'timelines': [{'create_time': tnow, 'id': did, 'is_marked_delete': False, 'name': 'Timeline 01', 'update_time': tnow}],
               'update_time': tnow, 'version': 0}, open(f'{out_dir}/Timelines/project.json', 'w'))
    json.dump({'dockItems': [{'dockIndex': 0, 'ratio': 1, 'timelineIds': [did], 'timelineNames': ['Timeline 01']}], 'layoutOrientation': 1},
              open(f'{out_dir}/timeline_layout.json', 'w'))
    open(f'{out_dir}/draft_settings', 'w').write(f'[General]\ncloud_last_modify_platform=mac\ndraft_create_time={now}\ndraft_last_edit_time={now}\nreal_edit_keys=0\nreal_edit_seconds=0\n')
    json.dump({'is_auto_agency_enabled': False, 'is_auto_agency_popup': False, 'is_single_agency_mode': False, 'marterials': None,
               'use_converter': False, 'video_resolution': 720}, open(f'{out_dir}/draft_agency_config.json', 'w'))
    meta = copy.deepcopy(TPL_META)
    mid = U()
    meta.update({'draft_id': mid, 'draft_name': name, 'draft_fold_path': fold, 'draft_cover': '', 'tm_draft_create': tnow,
                 'tm_draft_modified': tnow, 'tm_duration': d['duration'], 'draft_timeline_materials_size_': 0})
    items = []
    for it in meta_items:
        items.append({'ai_group_type': '', 'create_time': now, 'duration': it['duration'], 'enter_from': 0,
                      'extra_info': os.path.basename(it['file_Path']), 'file_Path': it['file_Path'], 'height': it['height'],
                      'id': u(), 'import_time': now, 'import_time_ms': tnow, 'item_source': 1, 'material_color_tag': '', 'md5': '',
                      'metetype': it['metetype'], 'roughcut_time_range': {'duration': it['duration'], 'start': 0},
                      'sub_time_range': {'duration': -1, 'start': -1}, 'type': 0, 'width': it['width']})
    meta['draft_materials'] = [{'type': 0, 'value': items}] + [{'type': t, 'value': []} for t in (1, 2, 3, 6, 7, 8)]
    json.dump(meta, open(f'{out_dir}/draft_meta_info.json', 'w'), ensure_ascii=False)
    root_entry = {k: v for k, v in json.load(open(f'{HERE}/root_meta_info.orig.json'))['all_draft_store'][0].items()}
    root_entry.update({'draft_cover': '', 'draft_fold_path': fold, 'draft_id': mid, 'draft_json_file': f'{fold}/draft_info.json',
                       'draft_name': name, 'draft_timeline_materials_size': 0, 'tm_draft_create': tnow, 'tm_draft_modified': tnow,
                       'tm_duration': d['duration']})
    return root_entry
