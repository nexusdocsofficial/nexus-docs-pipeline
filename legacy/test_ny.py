import json, sys, os, shutil, subprocess, importlib.util
from PIL import Image
sys.path.insert(0, '/home/claude/nexus/capcut'); import build_capcut as B
spec=importlib.util.spec_from_file_location('rl','/home/claude/nexus/03-newyork/render_long.py');rl=importlib.util.module_from_spec(spec)
sys.argv=['x','none'];spec.loader.exec_module(rl)
NAME='Nexus Docs test - New York'
MEDIA_MAC='/Users/USER/flow-mcp-out/03-NY-capcut-test'
STAGE='/mnt/user-data/outputs/capcut-test'
shutil.rmtree(STAGE, ignore_errors=True); os.makedirs(f'{STAGE}/media'); os.makedirs(f'{STAGE}/draft')
END=58.76
shots=[]; PAT=['in','out','in','in','out','in']
for s in rl.shots:
    if s['start']>=END-0.01: break
    src=rl.src_for(s)
    if src.startswith('/mnt/user-data/uploads/'):
        mac=src.replace('/mnt/user-data/uploads','/Users/USER')
    else:
        fn=f"shot{s['n']:03d}.jpg"; shutil.copy(src,f'{STAGE}/media/{fn}'); mac=f'{MEDIA_MAC}/{fn}'
    w,h=Image.open(src).size
    if s['kind']=='card':
        pts=rl.FOCUS[str(s['card'])]; anc=(sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
        z=(1.0,1.07 if len(pts)==1 else 1.04)
    else:
        anc=None; Z=0.03 if s['dur']>=3 else 0.015
        z=(1.01,1.01+Z) if PAT[s['n']%6]=='in' else (1.01+Z,1.01)
    shots.append({'path':mac,'w':w,'h':h,'start':s['start'],'dur':s['end']-s['start'],'zoom':z,'anchor':anc})
OUT='/home/claude/nexus/03-newyork/render_long'
stems=[]
for nm,src,fn in [('Voice-over','/home/claude/nexus/03-newyork/vo_long.wav','vo.m4a'),('Music',f'{OUT}/music_track.wav','music.m4a'),
                  ('Ambience',f'{OUT}/amb_track.wav','ambience.m4a'),('SFX',f'{OUT}/sfx_track.wav','sfx.m4a')]:
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',src,'-t',f'{END:.3f}','-af','volume=4dB','-ac','2','-ar','48000','-c:a','aac','-b:a','192k',f'{STAGE}/media/{fn}'],check=True)
    stems.append({'name':nm,'path':f'{MEDIA_MAC}/{fn}','dur':END,'volume':1.0})
entry=B.build(NAME,shots,stems,f'{STAGE}/draft')
root=json.load(open('/home/claude/nexus/capcut/root_meta_info.orig.json'))
root['all_draft_store'].insert(0,entry); root['draft_ids']=len(root['all_draft_store'])
json.dump(root,open(f'{STAGE}/root_meta_info.json','w'),ensure_ascii=False)
print(len(shots),'shots')
for r,_,fs in os.walk(STAGE):
    for f in fs: print(os.path.join(r,f).replace(STAGE+'/',''), os.path.getsize(os.path.join(r,f)))
