"""Beeldenlijst lange versie video 3. Hergebruikt de 74 oude shots (via shotmap.json) en voegt nieuwe shots + hoofdstukkaarten toe."""
import json, re

W = json.load(open('words_long.json'))
OLDSHOTS = json.load(open('shotlist.json'))
CH = json.load(open('chapters.json'))
norm = lambda w: re.sub(r'[^\w]', '', w).lower()

BASE = ("Hand-drawn stickman cartoon, 16:9 full frame: round white heads with simple visible faces, thick black outlines, "
        "flat vibrant colors, soft shading, simple flat backgrounds.")
T = {"A": "Fully colored scene: {p}", "B": "Plain pure white background, minimal: {p}",
     "C": "Hand-drawn map, beige land, soft blue water, clear colored regions: {p}",
     "D": "{p} Parchment scroll banner at the top reading \"{t}\".",
     "F": "Dark charcoal background with soft red glowing cracks. {p} A torn parchment strip across the center with bold text \"{t}\"."}
ERA = {
 'nl17': "Clothing 1600s Dutch: dark doublets with wide white collars, breeches, tall black hats; soldiers with morion helmets. No modern clothes.",
 'en17': "Clothing 1660s: English officers in long curly wigs, long coats and lace cravats; English sailors in loose shirts and caps. No modern clothes.",
 'lenape': "Clothing 1620s: Lenape in deerskin tunics, leggings, moccasins and wampum necklaces, drawn with dignity and respect, no stereotypes; Dutch in dark doublets with white collars and tall black hats. No modern clothes.",
 'c1700': "Clothing 1700s: Dutch merchants in long coats, waistcoats, tricorn hats and powdered wigs. No modern clothes.",
 'br1810': "Clothing 1810: British soldiers in red coats with white cross belts and tall black shako hats; Royal Navy sailors in striped shirts and straw hats. No modern clothes.",
 'now': "Modern casual clothing.", 'none': "No people in the image."}
NL = "a Dutch stickman in a black doublet with a wide flat white collar and a tall black hat"
HUDSON = "an English sea captain stickman with a short pointed beard, a dark 1600s doublet with a white ruff collar and a wide-brimmed hat"
STUY = "a stern older stickman governor with a wooden peg leg, a black doublet with a wide white collar, a sword at his side and a tall black hat"

# (startphrase in long VO, type, era, label, scene) — alleen NIEUWE shots; ze worden tussen de oude shots gevoegd
NEW = [
 ("His orders were clear", "C", "none", None, "a map of northern Europe and Russia: a dotted route starts at Amsterdam and goes north-east over the top of Russia toward Asia, but is blocked by big blue-white ice blocks with a red X."),
 ("But the ice blocked", "A", "nl17", None, "a small 1600s Dutch sailing ship with orange, white and blue flags stuck between huge white ice floes in a grey freezing sea, sailors looking worried."),
 ("So Hudson did something", "A", "nl17", None, f"on a 1600s ship in icy grey water, {HUDSON} turning the big wooden ship's wheel hard, determined face, the ship turning away from icebergs toward a sunset in the west."),
 ("He turned his ship around", "A", "nl17", None, "a 1600s Dutch sailing ship with orange, white and blue flags sailing west across a wide calm ocean toward a golden sunset, seagulls."),
 ("Hudson himself never saw", "B", "nl17", None, f"{HUDSON} standing empty-handed and sad on one side, while on the other side happy Amsterdam merchants hold beaver-fur hats and bags of gold coins."),
 ("Two years later,", "A", "nl17", None, f"on the deck of a 1600s ship trapped in a frozen bay, an angry crew of sailors in rough 1600s clothes confronting {HUDSON}, who looks shocked."),
 ("They put him in a small boat", "A", "nl17", None, f"a small open rowing boat drifting alone among ice floes in grey water, {HUDSON} and a young boy (his son) sitting in it, a big sailing ship sailing away in the distance."),
 ("A fort. A windmill.", "REUSE:27", None, None, "hergebruik oud shot 27 (bouw van fort, molen en grachten)"),
 ("But the river he found", "REUSE:12", None, None, "hergebruik oud shot 12 (kaart HUDSON RIVER)"),
 ("To them, land was a bit like", "A", "lenape", None, "a Lenape stickman standing on a hill with open arms, looking at a wide landscape of forest, river and sky with birds, peaceful and calm."),
 ("Two very different ideas", "B", "lenape", None, f"two panels side by side: on the left {NL} holding a paper deed with a big word \"OWNED\"; on the right a Lenape stickman with open arms in front of a tree with the word \"SHARED\"."),
 ("And not only Europe.", "A", "nl17", None, "a French Jesuit priest stickman in a long black cassock arriving in a small 1640s Dutch harbor town and talking with a Dutch official in a black doublet with a white collar."),
 ("was told that people there", "B", "nl17", None, "many cartoon speech bubbles in different colors floating together, each with different simple symbols and letters from different alphabets, and a big bold number \"18\" in the middle."),
 ("A noisy, messy harbor town", "A", "nl17", None, "a lively, crowded 1640s harbor street of New Amsterdam full of traders of many backgrounds (Dutch, English, French, African, Lenape) bargaining over barrels, furs and fish, ships behind, chickens and pigs in the street."),
 ("Almost anyone. In 1647,", "D", "nl17", "1647", f"Fully colored scene: {STUY} stepping off a ship onto the wooden dock of a small colonial town, townspeople watching curiously."),
 ("He had lost a leg", "B", "nl17", None, f"{STUY} standing proudly, close view, his wooden peg leg clearly visible, tapping it with his walking cane."),
 ("And he wanted order.", "A", "nl17", None, f"{STUY} standing stiffly in front of a single plain church, holding up a long scroll of rules, pointing at it sternly."),
 ("Twice, he tried", "A", "nl17", None, f"a small group of Jewish refugee families in plain 1650s clothing with bundles and chests arriving on a dock from a ship, and {STUY} holding up his hand to stop them; drawn with dignity and respect."),
 ("Then the Quakers,", "A", "nl17", None, "a few Quakers in very plain grey 1650s clothing and simple wide hats quietly meeting in a small wooden house, while a Dutch soldier nails a notice reading \"FORBIDDEN\" on the door."),
 ("And twice, the company", "A", "nl17", None, f"in a grand Amsterdam office, Dutch company directors in black at a long table writing a letter; the letter flies across the sea to {STUY}, who reads it with a frown."),
 ("For them, trade mattered", "B", "none", None, "a balance scale tipping down on the side with a big pile of gold coins and trade goods, the other side with a small church goes up."),
 ("The people of the village", "A", "nl17", None, "Dutch and English villagers in 1650s clothing gathered around a wooden table in a village house, one of them signing a long letter with a quill, the others nodding."),
 ("Today, it is remembered", "B", "none", None, "an old handwritten letter on yellowed paper with a soft golden glow, and next to it a modern scroll with the words \"FREEDOM OF RELIGION\"."),
 ("But this clash,", "B", "nl17", None, f"on the left {STUY} with arms crossed and a stern face; on the right a group of townspeople with arms crossed; a small cartoon lightning bolt between them."),
 ("England and the Dutch Republic", "B", "en17", None, "an English officer in a long curly wig sneakily reaching for a small island with a little Dutch town on it, while a peace dove sits between an English flag (red cross on white) and an old Dutch flag (orange, white and blue)."),
 ("The English simply wanted", "A", "en17", None, "an English naval officer in a long curly wig on a warship, greedily looking through a spyglass at a small Dutch harbor town with a fine natural harbor."),
 ("They had their homes", "A", "nl17", None, "Dutch townspeople, men, women and children, standing protectively in front of their step-gabled houses and small shops, worried faces, looking toward the harbor."),
 ("So valuable, that", "F", "none", "1621 - BANDA", ""),
 ("In 1621, Dutch company soldiers", "A", "nl17", None, "several 1600s Dutch warships anchored off green tropical islands with volcano peaks, small boats full of soldiers heading to the beach, dark clouds and smoke in the distance; no blood, no visible violence."),
 ("Most of the people", "C", "none", None, "a map of a small group of tropical islands; on the left side many small figure icons, on the right side the same islands with only a few faded figure icons left, a somber grey tone."),
 ("It is one of the darkest", "B", "none", None, "a single burning candle next to a small branch of a nutmeg tree, quiet and solemn mood, soft grey shadows."),
 ("Only one tiny island", "C", "none", None, "a map of the small tropical nutmeg islands: all islands colored in Dutch orange except one tiny island on the left, colored English red with a tiny English flag and labeled \"RUN\"."),
 ("Then, the Dutch found", "A", "nl17", None, "a Dutch admiral stickman in a 1660s dark coat with an orange sash and a wide hat on his ship, pointing at a map of England with a determined smile, officers around him."),
 ("A Dutch fleet sailed right up", "C", "none", None, "a map of the North Sea between the Netherlands and England with a bold orange arrow and small Dutch ship icons going from Holland straight into the mouth of the river Thames, labeled \"THAMES\"."),
 ("They burned English warships", "A", "en17", None, "on a river at dusk, Dutch warships with orange flags sailing past burning English warships, while a big decorated English flagship is towed away by Dutch boats; dramatic but not gory."),
 ("Part of that ship", "A", "now", None, "a modern museum hall with a huge colorful carved wooden royal coat of arms (a lion and a unicorn holding a shield) hanging on the wall, modern stickman visitors looking at it with amazement."),
 ("England needed peace", "B", "en17", None, "an English king stickman with a long curly black wig and a crown, sweating nervously, quickly signing a peace paper with a quill."),
 ("So, who really won", "B", "none", None, "a big balance scale: on one side a small green island with a little town (Manhattan), on the other side a tiny tropical island with a nutmeg tree, a big question mark above the scale."),
 ("For more than a century", "A", "c1700", None, "rich Dutch merchants in a 1700s Amsterdam counting house counting gold coins next to big sacks labeled \"NUTMEG\", happy faces."),
 ("Nutmeg kept their company rich", "A", "c1700", None, "a small 1700s colonial port town with a few wooden ships, a church spire and modest brick houses by the water, quiet and calm."),
 ("But in 1810,", "D", "br1810", "1810", "Fully colored scene: British warships with British flags anchored off green tropical islands, red-coated British soldiers marching onto the beach of the spice islands."),
 ("And this time, they took", "A", "br1810", None, "British sailors carefully carrying small potted nutmeg seedlings up a gangplank onto a sailing ship, one sailor winking."),
 ("They planted them", "C", "none", None, "a world map with dotted arrows starting from the small spice islands in Indonesia to other places: Sri Lanka, Malaysia (Penang) and the Caribbean island of Grenada, each with a small nutmeg tree icon."),
 ("Today, the island of Grenada", "A", "now", None, "the national flag of Grenada waving on a sunny Caribbean beach: red border with six yellow stars, two yellow and two green triangles, a red circle with a yellow star in the center and a small nutmeg on the left green triangle."),
 ("The Dutch monopoly was gone.", "B", "none", None, "an old wooden treasure chest full of nutmegs with a broken padlock hanging open."),
 ("Run slowly faded", "A", "now", None, "three stages side by side of the same harbor view growing over time: a small 1700s port, a busy 1800s city with sailing ships and brick buildings, and the giant modern Manhattan skyline."),
]

def find(phrase, start=0):
    ph = [norm(p) for p in phrase.split()]
    toks = [norm(w['w']) for w in W]
    for i in range(start, len(W)):
        if toks[i:i + len(ph)] == ph and W[i]['src'] != 'chap': return i
    raise SystemExit('not found ' + phrase)

cuts = []  # (time, kind, payload)
# old shots: start at the long-timeline time of their first old word
old_idx = {w['si']: i for i, w in enumerate(W) if w['src'] == 'old'}
SKIP_OLD = {27}
for s in OLDSHOTS:
    if s['n'] in SKIP_OLD: continue
    if s['type'] == 'O':
        i = old_idx[s['wi']]
        cuts.append((W[i]['start'], 'outro', s['n']))
        continue
    i = old_idx[s['wi']]
    cuts.append((0.0 if s['n'] == 1 else W[i]['start'], 'old', s['n']))
pos = 0
for k, (ph, typ, era, lab, scene) in enumerate(NEW):
    i = find(ph, 0)
    cuts.append((W[i]['start'], 'new', k))
for c in CH:
    cuts.append((c['start'] - 0.3, 'card', c['n']))
# v3: some images start later, exactly on the words they show
MOVE = {('old', 38): 'And this is where the nutmeg'}
for k, (t0, kind, p) in enumerate(cuts):
    if (kind, p) in MOVE:
        i = find(MOVE[(kind, p)], 0); cuts[k] = (W[i]['start'] - 0.1, kind, p)
cuts.sort(key=lambda x: x[0])

TOTAL = W[-1]['end'] + 0.6
shots = []
for j, (t0, kind, p) in enumerate(cuts):
    t1 = cuts[j + 1][0] if j + 1 < len(cuts) else TOTAL
    d = {'n': j + 1, 'start': round(t0, 3), 'end': round(t1, 3), 'dur': round(t1 - t0, 2), 'kind': kind}
    if kind == 'old':
        o = OLDSHOTS[p - 1]; d.update(old=p, type=o['type'], scene=o['scene'], label=o.get('label'))
    elif kind == 'new':
        ph, typ, era, lab, scene = NEW[p]
        if typ.startswith('REUSE'):
            d.update(old=int(typ.split(':')[1]), type='reuse', scene=scene)
        else:
            d.update(newk=p, type=typ, era=era, label=lab, scene=scene,
                     prompt=f"{BASE} {T[typ].format(p=scene.replace('Fully colored scene: ', ''), t=lab)} {ERA[era]}")
    elif kind == 'card':
        c = CH[p - 1]; d.update(card=p, type='card', scene=f"Hoofdstukkaart {p}: {c['title']}", label=c['title'])
    else:
        d.update(type='O', scene='Geanimeerde outro')
    ws = [w['w'] for w in W if t0 - 0.01 <= w['start'] < t1 - 0.01]
    d['text'] = ' '.join(ws)
    shots.append(d)
json.dump(shots, open('shotlist_long.json', 'w'), indent=1)
if __name__ == '__main__':
    for s in shots:
        flag = ' <<' if s['dur'] < 2.0 or s['dur'] > 7.0 else ''
        print(f"{s['n']:3d} {s['start']:6.1f} {s['dur']:5.1f} {s['kind'][:4]:4s} {s['type']:5s} | {s['text'][:60]}{flag}")
    print(len(shots), 'shots;', sum(1 for s in shots if s['kind'] == 'new' and s['type'] != 'reuse'), 'new images;', round(TOTAL, 1), 's')
