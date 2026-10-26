"""Chapter cards v2: big 'CHAPTER N' + title on the banner, a clear red map pin on the location."""
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
src='/mnt/user-data/uploads/flow-mcp-out/03-NY-anker/scene-01.jpeg'
base=Image.open(src).convert('RGB')
sx=1920/base.width; sy=1080/base.height
base=base.resize((1920,1080),Image.LANCZOS)
F='/home/claude/nexus/thumb/fonts/gf/ofl/patrickhand/PatrickHand-Regular.ttf'
P={'AMS':(607,207),'NA':(252,270),'RUN':(1222,483)}
P={k:(x*sx,y*sy) for k,(x,y) in P.items()}
CH=json.load(open('chapters.json'))
PINS={1:['AMS'],2:['NA'],3:['NA'],4:['NA'],5:['RUN'],6:['NA'],7:['NA','RUN']}
BX=697*sx

def pin(im, x, y, s=1.0):
    """red teardrop map pin whose tip touches (x, y)"""
    H=int(86*s); R=int(27*s)
    lay=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(lay)
    # soft shadow on the map
    sh=Image.new('RGBA',im.size,(0,0,0,0)); ds=ImageDraw.Draw(sh)
    ds.ellipse([x-18*s,y-6*s,x+18*s,y+6*s],fill=(0,0,0,110))
    sh=sh.filter(ImageFilter.GaussianBlur(4))
    cx,cy=x,y-H+R
    d.polygon([(x,y),(cx-R*0.82,cy+R*0.55),(cx+R*0.82,cy+R*0.55)],fill=(205,35,35),outline=(60,15,10))
    d.ellipse([cx-R,cy-R,cx+R,cy+R],fill=(205,35,35),outline=(60,15,10),width=max(3,int(4*s)))
    d.polygon([(x,y-2),(cx-R*0.70,cy+R*0.62),(cx+R*0.70,cy+R*0.62)],fill=(205,35,35))
    d.ellipse([cx-R*0.42,cy-R*0.42,cx+R*0.42,cy+R*0.42],fill=(255,248,235),outline=(60,15,10),width=2)
    d.ellipse([cx-R*0.62,cy-R*0.72,cx-R*0.25,cy-R*0.40],fill=(255,140,130))
    return Image.alpha_composite(Image.alpha_composite(im,sh),lay)

def fit(d, txt, maxw, size):
    while size>20:
        f=ImageFont.truetype(F,size)
        if d.textlength(txt,font=f)<=maxw: return f
        size-=2
    return ImageFont.truetype(F,size)

for c in CH:
    im=base.copy().convert('RGBA')
    # warm glow ring around each location
    glow=Image.new('RGBA',im.size,(0,0,0,0)); g=ImageDraw.Draw(glow)
    for k in PINS[c['n']]:
        x,y=P[k]
        for r,a in [(70,35),(50,55),(32,80)]:
            g.ellipse([x-r,y-r*0.6,x+r,y+r*0.6],fill=(255,170,40,a))
    im=Image.alpha_composite(im,glow.filter(ImageFilter.GaussianBlur(8)))
    NAMES={'AMS':'AMSTERDAM','NA':'NEW AMSTERDAM','RUN':'RUN'}
    for k in PINS[c['n']]:
        im=pin(im,*P[k],s=1.0)
        x,y=P[k]; dt=ImageDraw.Draw(im); ft=ImageFont.truetype(F,32)
        tw=dt.textlength(NAMES[k],font=ft); tx,ty=x+30,y-86
        dt.rounded_rectangle([tx,ty,tx+tw+24,ty+44],radius=10,fill=(255,250,238),outline=(70,45,25),width=3)
        dt.text((tx+12,ty+3),NAMES[k],font=ft,fill=(150,30,20))
    # big parchment plaque over the old banner
    pl=Image.new('RGBA',im.size,(0,0,0,0)); dp=ImageDraw.Draw(pl)
    x0,y0,x1,y1=BX-360,20,BX+360,192
    dp.rounded_rectangle([x0+6,y0+8,x1+6,y1+8],radius=26,fill=(0,0,0,70))
    pl=pl.filter(ImageFilter.GaussianBlur(5)); dp=ImageDraw.Draw(pl)
    dp.rounded_rectangle([x0,y0,x1,y1],radius=26,fill=(243,230,198,255),outline=(70,45,25,255),width=5)
    dp.rounded_rectangle([x0+12,y0+12,x1-12,y1-12],radius=18,outline=(150,110,70,255),width=2)
    im=Image.alpha_composite(im,pl)
    d=ImageDraw.Draw(im)
    t1=f"CHAPTER {c['n']}"; t2=c['title'].upper()
    f1=ImageFont.truetype(F,46); f2=fit(d,t2,640,74)
    for txt,f,y,col in [(t1,f1,y0+18,(165,70,20)),(t2,f2,y0+70,(30,20,10))]:
        w=d.textlength(txt,font=f)
        d.text((BX-w/2,y),txt,font=f,fill=col,stroke_width=1,stroke_fill=col)
    im.convert('RGB').save(f"cards/card-{c['n']}.jpg",quality=94)
json.dump({str(c['n']):[list(P[k]) for k in PINS[c['n']]] for c in CH},open('cards/focus.json','w'))
print('ok')
