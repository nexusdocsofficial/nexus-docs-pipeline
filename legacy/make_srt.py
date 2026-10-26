import json
W=json.load(open('words_long.json'))
def ts(t):
    h=int(t//3600); m=int(t%3600//60); s=t%60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s-int(s))*1000)):03d}".replace(',1000',',999')
cues=[]; cur=[]; 
def text(ws):
    out=''
    for w in ws:
        out += w['w'] if out.endswith('-') or not out else ' '+w['w']
    return out
for i,w in enumerate(W):
    cur.append(w)
    t=text(cur); nxt=W[i+1] if i+1<len(W) else None
    gap=(nxt['start']-w['end']) if nxt else 9
    end_s=w['w'][-1] in '.?!'; comma=w['w'][-1] in ',:;'
    if (not nxt) or gap>0.6 or (end_s and len(t)>18) or (comma and len(t)>30) or len(t)>40 or (cur[-1]['end']-cur[0]['start'])>3.6:
        cues.append((cur[0]['start'],min(w['end']+0.25,(nxt['start']-0.02) if nxt else w['end']+1),t)); cur=[]
with open('/mnt/user-data/outputs/03-new-york-en.srt','w') as f:
    for k,(a,b,t) in enumerate(cues,1): f.write(f"{k}\n{ts(a)} --> {ts(b)}\n{t}\n\n")
print(len(cues))
