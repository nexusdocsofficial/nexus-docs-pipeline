import json,subprocess,sys
sys.argv_backup=sys.argv
import importlib.util
spec=importlib.util.spec_from_file_location('rl','/home/claude/nexus/03-newyork/render_long.py');rl=importlib.util.module_from_spec(spec)
sys.argv=['x','none'];spec.loader.exec_module(rl);sys.argv=sys.argv_backup
S={s['n']:s for s in rl.shots}
out=sys.argv[1];ns=[int(x) for x in sys.argv[2].split(',')]
inp=[];f=[]
for i,n in enumerate(ns):
    inp+=['-i',rl.src_for(S[n])]
    f.append(f"[{i}]scale=480:270,drawtext=text='{n}':x=8:y=6:fontsize=34:fontcolor=red:borderw=3[v{i}]")
cols=4;rows=(len(ns)+cols-1)//cols;pad=rows*cols-len(ns)
for j in range(pad): f.append(f"color=white:s=480x270:d=1[p{j}]")
labels=''.join(f'[v{i}]' for i in range(len(ns)))+''.join(f'[p{j}]' for j in range(pad))
lay='|'.join(f'{(k%cols)*480}_{(k//cols)*270}' for k in range(rows*cols))
f.append(f"{labels}xstack=inputs={rows*cols}:layout={lay}")
subprocess.run(['ffmpeg','-loglevel','error','-y']+inp+['-filter_complex',';'.join(f),'-frames:v','1',out],check=True)
