"""Generates MYSTIQ's seven case-cover illustrations + hero scene as inline-SVG partials.
Colours are CSS variables (--bg, --acc, ...), so each case's theme re-colours its own artwork."""
import math, random, os
OUT = os.path.join(os.path.dirname(__file__), "..", "templates", "game", "art")
W, H = 800, 520

def wrap(n, body, defs=""):
    return (f'<svg class="art art-{n}" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" role="img" aria-hidden="true" '
            f'xmlns="http://www.w3.org/2000/svg"><defs>{defs}</defs>{body}</svg>')

def gear(cx, cy, r, teeth, depth, rot=0, tw=0.5):
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a = rot + i * step
        for da, rr in ((0, r - depth), (step * (0.5 - tw / 2) * 0.9, r - depth), (step * (0.5 - tw / 2) , r), (step * (0.5 + tw / 2) , r), (step * (0.5 + tw / 2) * 1.0 + step * 0.04, r - depth)):
            pts.append((cx + rr * math.cos(a + da), cy + rr * math.sin(a + da)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"

def sparkle(x, y, s, fill="var(--acc)", o=.9):
    return f'<path d="M{x} {y-s}L{x+s*.22} {y-s*.22}L{x+s} {y}L{x+s*.22} {y+s*.22}L{x} {y+s}L{x-s*.22} {y+s*.22}L{x-s} {y}L{x-s*.22} {y-s*.22}Z" fill="{fill}" opacity="{o}"/>'

# ------------------------------------------------------------------ 1 Emerald
def c1():
    n = 1; r = random.Random(11)
    defs = f'''<radialGradient id="c1g" cx=".5" cy=".48" r=".6"><stop offset="0" stop-color="var(--acc)" stop-opacity=".55"/><stop offset=".55" stop-color="var(--acc)" stop-opacity=".08"/><stop offset="1" stop-color="var(--bg)" stop-opacity="0"/></radialGradient>
<linearGradient id="c1e" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7ff0c0"/><stop offset=".45" stop-color="var(--acc)"/><stop offset="1" stop-color="#0c6a47"/></linearGradient>
<linearGradient id="c1b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e9d79a"/><stop offset="1" stop-color="var(--acc2)"/></linearGradient>'''
    b = f'<rect width="800" height="520" fill="var(--bg)"/><rect width="800" height="520" fill="url(#c1g)"/>'
    # lattice
    for i in range(-6, 14):
        b += f'<path d="M{i*70} 0L{i*70+260} 520" stroke="var(--acc2)" stroke-opacity=".07" stroke-width="1"/><path d="M{i*70+260} 0L{i*70} 520" stroke="var(--acc2)" stroke-opacity=".07" stroke-width="1"/>'
    # arch window
    b += '<path d="M265 470V170Q265 55 400 55Q535 55 535 170V470Z" fill="var(--bg2)" stroke="url(#c1b)" stroke-width="4"/>'
    b += '<path d="M285 470V175Q285 75 400 75Q515 75 515 175V470Z" fill="none" stroke="var(--acc2)" stroke-opacity=".5" stroke-width="1.5"/>'
    b += '<path d="M400 75V470M285 250H515" stroke="var(--acc2)" stroke-opacity=".35" stroke-width="2"/>'
    for k in range(14):
        a = k * math.pi / 7
        b += f'<path d="M400 250L{400+330*math.cos(a):.0f} {250+330*math.sin(a):.0f}" stroke="var(--acc)" stroke-opacity=".11" stroke-width="{2 + (k%2)*3}"/>'
    # plinth
    b += '<path d="M300 420H500L520 470H280Z" fill="var(--surf)" stroke="url(#c1b)" stroke-width="2"/><rect x="270" y="470" width="260" height="14" fill="var(--bg2)" stroke="var(--acc2)" stroke-opacity=".6"/>'
    b += '<ellipse cx="400" cy="420" rx="100" ry="11" fill="var(--bg)" opacity=".8"/>'
    # gem emerald cut
    cx, cy = 400, 288
    def octo(w, h, c):
        return f'{cx-w+c},{cy-h} {cx+w-c},{cy-h} {cx+w},{cy-h+c} {cx+w},{cy+h-c} {cx+w-c},{cy+h} {cx-w+c},{cy+h} {cx-w},{cy+h-c} {cx-w},{cy-h+c}'
    b += f'<polygon points="{octo(100,130,38)}" fill="url(#c1e)" stroke="#bff5dc" stroke-opacity=".7" stroke-width="2"/>'
    b += f'<polygon points="{octo(72,100,26)}" fill="none" stroke="#d6fbe9" stroke-opacity=".55" stroke-width="1.6"/>'
    b += f'<polygon points="{octo(44,70,16)}" fill="#0a5c3f" fill-opacity=".55" stroke="#d6fbe9" stroke-opacity=".7" stroke-width="1.6"/>'
    for (x1, y1, x2, y2) in [(-100,-92,-72,-74),(100,-92,72,-74),(-100,92,-72,74),(100,92,72,74),(-62,-130,-44,-100),(62,-130,44,-100),(-62,130,-44,100),(62,130,44,100)]:
        b += f'<path d="M{cx+x1} {cy+y1}L{cx+x2} {cy+y2}" stroke="#d6fbe9" stroke-opacity=".5" stroke-width="1.4"/>'
    b += f'<polygon points="{cx-70},{cy-120} {cx-10},{cy-120} {cx-60},{cy-40} {cx-84},{cy-40}" fill="#fff" opacity=".22"/><polygon points="{cx+30},{cy+100} {cx+80},{cy+60} {cx+80},{cy+90} {cx+60},{cy+110}" fill="#fff" opacity=".14"/>'
    # key
    b += '<g transform="translate(105 395) rotate(-24)"><circle cx="0" cy="0" r="30" fill="none" stroke="url(#c1b)" stroke-width="9"/><circle cx="0" cy="0" r="12" fill="none" stroke="url(#c1b)" stroke-width="4"/><rect x="28" y="-5" width="150" height="10" rx="3" fill="url(#c1b)"/><path d="M130 5h14v26h-14zM152 5h12v18h-12z" fill="url(#c1b)"/></g>'
    # house silhouette
    b += '<path d="M0 520V455H50V430H70V400H92V430H130V440H180V415L200 395L220 415V440H640V412L664 388L688 412V440H720V420H742V398H764V430H800V520Z" fill="var(--bg)"/>'
    for x in (92, 200, 664, 750, 300, 380, 560):
        b += f'<rect x="{x-6}" y="{450 if x not in (92,200,664,750) else 410}" width="10" height="18" fill="var(--acc2)" opacity=".75"/>'
    for _ in range(26):
        b += sparkle(r.randint(30, 770), r.randint(30, 400), r.choice([5, 7, 9]), "var(--acc2)" if r.random() < .5 else "#cffff0", r.choice([.35, .6, .9]))
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 2 Midnight Letter
def c2():
    n = 2; r = random.Random(22)
    defs = '''<linearGradient id="c2s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#101a44"/><stop offset="1" stop-color="var(--bg)"/></linearGradient>
<radialGradient id="c2m" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="var(--acc)" stop-opacity=".55"/><stop offset="1" stop-color="var(--acc)" stop-opacity="0"/></radialGradient>'''
    b = '<rect width="800" height="520" fill="url(#c2s)"/>'
    for _ in range(70):
        b += f'<circle cx="{r.randint(0,800)}" cy="{r.randint(0,330)}" r="{r.choice([.8,1,1.3,1.8])}" fill="var(--acc)" opacity="{r.choice([.3,.5,.8])}"/>'
    b += '<circle cx="560" cy="120" r="120" fill="url(#c2m)"/><path d="M560 74A46 46 0 1 0 596 150A38 38 0 1 1 560 74Z" fill="var(--acc)"/>'
    # window
    b += '<g stroke="var(--line)" stroke-width="5" fill="none"><rect x="215" y="28" width="370" height="330" rx="4"/><path d="M400 28V358M215 193H585"/></g><g fill="var(--bg)" opacity=".5"><rect x="205" y="360" width="390" height="22"/></g>'
    # ink lines of rain
    for i in range(16):
        x = 230 + i * 22
        b += f'<path d="M{x} {40+ (i*37)%90}v{30+(i*13)%40}" stroke="var(--acc)" stroke-opacity=".18" stroke-width="1.2"/>'
    # pages
    b += '<g transform="translate(330 250) rotate(-14)"><rect width="190" height="240" fill="var(--paper)" opacity=".75"/>' + ''.join(f'<rect x="20" y="{30+i*22}" width="{120+(i*29)%40}" height="3" fill="var(--bg)" opacity=".5"/>' for i in range(8)) + '</g>'
    b += '<g transform="translate(440 238) rotate(11)"><rect width="190" height="240" fill="var(--paper)" opacity=".6"/>' + ''.join(f'<rect x="20" y="{30+i*22}" width="{110+(i*17)%50}" height="3" fill="var(--bg)" opacity=".45"/>' for i in range(8)) + '</g>'
    # envelope
    b += '<g transform="translate(400 330) rotate(-5)"><rect x="-170" y="-105" width="340" height="210" fill="var(--paper)"/><path d="M-170 -105L0 20L170 -105" fill="none" stroke="var(--bg)" stroke-opacity=".35" stroke-width="2"/><path d="M-170 105L-30 -5M170 105L30 -5" stroke="var(--bg)" stroke-opacity=".3" stroke-width="2"/><path d="M-170 -105H170L0 20Z" fill="var(--paper)" stroke="var(--bg)" stroke-opacity=".25"/>'
    b += '<circle cx="0" cy="22" r="36" fill="var(--acc2)"/><circle cx="0" cy="22" r="28" fill="none" stroke="#00000055" stroke-width="2"/><path d="M0 4l6 12 13 2-10 9 3 13-12-7-12 7 3-13-10-9 13-2Z" fill="#00000040"/><path d="M-14 56q-8 28 -2 46M18 52q8 22 4 40" stroke="var(--acc2)" stroke-width="7" stroke-linecap="round" fill="none"/><circle cx="-16" cy="104" r="6" fill="var(--acc2)"/></g>'
    # ink drop
    b += '<path d="M268 460q-12 24 0 36q12 -12 0 -36Z" fill="var(--acc2)" opacity=".8"/>'
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 3 Locked Library
def c3():
    n = 3; r = random.Random(33)
    defs = '''<radialGradient id="c3g" cx=".5" cy=".62" r=".55"><stop offset="0" stop-color="var(--acc)" stop-opacity=".55"/><stop offset="1" stop-color="var(--acc)" stop-opacity="0"/></radialGradient>
<clipPath id="c3c"><path d="M215 520V170Q215 40 400 40Q585 40 585 170V520Z"/></clipPath>'''
    b = '<rect width="800" height="520" fill="var(--bg)"/>'
    for i in range(0, 800, 80):
        b += f'<path d="M{i} 520V300Q{i+40} 250 {i+80} 300V520" fill="none" stroke="var(--line)" stroke-opacity=".5"/>'
    b += '<path d="M215 520V170Q215 40 400 40Q585 40 585 170V520Z" fill="var(--bg2)"/><g clip-path="url(#c3c)">'
    cols = ["var(--acc2)", "#7a2230", "#4a2118", "#8a5a2a", "#2f1a16", "#a63a3a", "#5a3a2a", "#c98a3a"]
    for si, y in enumerate((120, 210, 300, 390)):
        x = 215
        while x < 585:
            w = r.randint(10, 22); h = r.randint(54, 76)
            b += f'<rect x="{x}" y="{y+86-h-8}" width="{w}" height="{h}" fill="{r.choice(cols)}" stroke="var(--bg)" stroke-width="1.2"/><rect x="{x+2}" y="{y+86-h-2}" width="{w-4}" height="3" fill="var(--acc)" opacity=".5"/>'
            x += w + r.choice([0, 0, 2, 5])
        b += f'<rect x="215" y="{y+78}" width="370" height="9" fill="#2a130f"/><rect x="215" y="{y+78}" width="370" height="2" fill="var(--acc2)" opacity=".5"/>'
    b += '</g><path d="M215 520V170Q215 40 400 40Q585 40 585 170V520Z" fill="none" stroke="var(--acc2)" stroke-width="5"/>'
    b += '<rect width="800" height="520" fill="url(#c3g)"/>'
    # clock
    b += '<circle cx="400" cy="96" r="44" fill="var(--bg)" stroke="var(--acc)" stroke-width="4"/><circle cx="400" cy="96" r="36" fill="#f6e8c9"/>' + ''.join(f'<path d="M{400+30*math.cos(k*math.pi/6):.1f} {96+30*math.sin(k*math.pi/6):.1f}L{400+35*math.cos(k*math.pi/6):.1f} {96+35*math.sin(k*math.pi/6):.1f}" stroke="#2a130f" stroke-width="2"/>' for k in range(12)) + '<path d="M400 96L400 70M400 96L418 108" stroke="#2a130f" stroke-width="3.5" stroke-linecap="round"/>'
    # padlock + chain
    b += '<path d="M330 330Q400 355 470 330" fill="none" stroke="var(--acc)" stroke-width="8" stroke-dasharray="14 6"/><path d="M372 322v-34a28 28 0 0 1 56 0v34" fill="none" stroke="var(--acc)" stroke-width="12"/><rect x="352" y="318" width="96" height="78" rx="8" fill="var(--acc2)"/><rect x="352" y="318" width="96" height="78" rx="8" fill="none" stroke="#00000066" stroke-width="2"/><circle cx="400" cy="350" r="9" fill="#2a130f"/><path d="M396 354h8l3 22h-14z" fill="#2a130f"/>'
    # candle
    b += '<rect x="108" y="410" width="20" height="90" fill="#f1e2c0"/><rect x="100" y="500" width="36" height="8" fill="var(--acc2)"/><path d="M118 410q-14 -26 0 -54q14 28 0 54Z" fill="var(--acc)"/><path d="M118 404q-6 -14 0 -30q6 16 0 30Z" fill="#fff4cf"/><circle cx="118" cy="384" r="70" fill="var(--acc)" opacity=".14"/>'
    # ladder
    b += '<path d="M650 520L690 170M690 520L730 170" stroke="var(--acc2)" stroke-width="7" opacity=".7"/>' + ''.join(f'<path d="M{652+i*40*0.2*0+ (i*7.4):.0f} {500-i*55}H{692+ i*7.4:.0f}" stroke="var(--acc2)" stroke-width="5" opacity=".7"/>' for i in range(6))
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 4 Railway
def c4():
    n = 4; r = random.Random(44)
    defs = '''<linearGradient id="c4s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b3330"/><stop offset="1" stop-color="var(--bg)"/></linearGradient>
<filter id="c4b"><feGaussianBlur stdDeviation="9"/></filter><radialGradient id="c4l" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffe9b0" stop-opacity=".9"/><stop offset="1" stop-color="#ffe9b0" stop-opacity="0"/></radialGradient>'''
    b = '<rect width="800" height="520" fill="url(#c4s)"/>'
    for (x, y, rr) in [(260, 110, 60), (330, 90, 80), (420, 120, 70), (520, 85, 60), (600, 120, 55), (200, 160, 45)]:
        b += f'<circle cx="{x}" cy="{y}" r="{rr}" fill="#aab4ae" opacity=".22" filter="url(#c4b)"/>'
    # platform & track
    b += '<rect y="418" width="800" height="102" fill="#0c0f0e"/><rect y="410" width="800" height="9" fill="var(--acc)" opacity=".7"/><rect y="404" width="800" height="6" fill="#c9c9c1" opacity=".5"/>'
    b += '<path d="M0 470H800M0 492H800" stroke="#6c756f" stroke-width="4"/>' + ''.join(f'<rect x="{i*52-10}" y="480" width="34" height="9" fill="#2c3330"/>' for i in range(17))
    # carriage
    b += '<rect x="40" y="228" width="720" height="176" rx="14" fill="var(--acc2)"/><rect x="40" y="228" width="720" height="176" rx="14" fill="none" stroke="var(--acc)" stroke-width="3"/><rect x="40" y="338" width="720" height="10" fill="var(--acc)" opacity=".8"/><rect x="40" y="388" width="720" height="16" fill="#0c120f"/>'
    for i in range(6):
        x = 78 + i * 116
        lit = i != 3
        b += f'<rect x="{x}" y="256" width="82" height="72" rx="8" fill="{ "#ffe7a8" if lit else "#101412"}" stroke="var(--acc)" stroke-width="3"/>'
        if lit:
            b += f'<circle cx="{x+30}" cy="296" r="9" fill="#2b2118" opacity=".8"/><path d="M{x+12} 328q18 -24 36 0Z" fill="#2b2118" opacity=".8"/>' if i in (1, 5) else ''
            b += f'<rect x="{x}" y="256" width="82" height="72" rx="8" fill="url(#c4l)" opacity=".4"/>'
        else:
            b += f'<rect x="{x+16}" y="300" width="50" height="28" rx="3" fill="#0a0d0b" stroke="#2c3330"/><path d="M{x+22} 300q12 -26 40 0Z" fill="#1c2420"/><rect x="{x+26}" y="286" width="30" height="5" rx="2" fill="#2c3330"/>'
    b += '<g fill="#0c0f0e">' + ''.join(f'<circle cx="{x}" cy="410" r="15"/>' for x in (130, 190, 610, 670)) + '</g><g fill="none" stroke="#6c756f" stroke-width="3">' + ''.join(f'<circle cx="{x}" cy="410" r="9"/>' for x in (130, 190, 610, 670)) + '</g>'
    # clock on pole
    b += '<rect x="396" y="130" width="8" height="280" fill="#0c0f0e"/><circle cx="400" cy="130" r="40" fill="#0c0f0e" stroke="var(--acc)" stroke-width="4"/><circle cx="400" cy="130" r="32" fill="#efe9d8"/>' + ''.join(f'<path d="M{400+26*math.cos(k*math.pi/6):.1f} {130+26*math.sin(k*math.pi/6):.1f}L{400+31*math.cos(k*math.pi/6):.1f} {130+31*math.sin(k*math.pi/6):.1f}" stroke="#111" stroke-width="2"/>' for k in range(12)) + '<path d="M400 130L400 106M400 130L418 142" stroke="#111" stroke-width="3.5" stroke-linecap="round"/>'
    # signal
    b += '<rect x="688" y="70" width="8" height="338" fill="#0c0f0e"/><rect x="664" y="86" width="56" height="86" rx="10" fill="#0c0f0e" stroke="#6c756f" stroke-width="2"/><circle cx="692" cy="112" r="15" fill="var(--sig)"/><circle cx="692" cy="112" r="38" fill="var(--sig)" opacity=".22"/><circle cx="692" cy="150" r="10" fill="#1d2420"/>'
    b += '<g transform="translate(110 100) rotate(-8)"><rect width="76" height="52" rx="4" fill="#2c3330" stroke="var(--acc)" stroke-width="2"/><rect x="26" y="-14" width="24" height="14" rx="3" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M8 40h60" stroke="var(--acc)" stroke-width="3"/></g>'
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 5 Clockwork
def c5():
    n = 5
    defs = '''<radialGradient id="c5g" cx=".5" cy=".5" r=".6"><stop offset="0" stop-color="var(--acc)" stop-opacity=".3"/><stop offset="1" stop-color="var(--bg)" stop-opacity="0"/></radialGradient>
<linearGradient id="c5c" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0a26a"/><stop offset="1" stop-color="#8a3f17"/></linearGradient><linearGradient id="c5t" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5de0d8"/><stop offset="1" stop-color="#136b68"/></linearGradient>'''
    b = '<rect width="800" height="520" fill="var(--bg)"/><rect width="800" height="520" fill="url(#c5g)"/>'
    for i in range(10):
        b += f'<circle cx="400" cy="260" r="{60+i*45}" fill="none" stroke="var(--line)" stroke-opacity=".45" stroke-dasharray="2 8"/>'
    def g(cx, cy, r, t, d, fill, rot=0, hole=.45, spokes=6):
        s = f'<path d="{gear(cx,cy,r,t,d,rot)}" fill="{fill}" stroke="#00000055" stroke-width="2"/><circle cx="{cx}" cy="{cy}" r="{r*hole:.0f}" fill="var(--bg)" opacity=".92"/>'
        for k in range(spokes):
            a = rot + k * 2 * math.pi / spokes
            s += f'<path d="M{cx} {cy}L{cx+(r*hole)*math.cos(a):.1f} {cy+(r*hole)*math.sin(a):.1f}" stroke="{fill}" stroke-width="{max(4, r/18):.0f}"/>'
        return s + f'<circle cx="{cx}" cy="{cy}" r="{r*.12:.0f}" fill="{fill}"/>'
    b += g(610, 112, 86, 12, 15, "url(#c5t)", .2, .5, 5) + g(215, 410, 96, 14, 16, "url(#c5c)", .1, .5, 5) + g(640, 420, 52, 9, 11, "url(#c5c)", .3, .4, 4)
    cx, cy = 400, 262
    b += f'<path d="{gear(cx,cy,176,22,20,0.05)}" fill="url(#c5c)" stroke="#00000066" stroke-width="3"/><circle cx="{cx}" cy="{cy}" r="146" fill="var(--bg2)" stroke="var(--acc)" stroke-width="4"/><circle cx="{cx}" cy="{cy}" r="128" fill="#f1e8d6"/>'
    for k in range(60):
        a = k * math.pi / 30; l = 14 if k % 5 == 0 else 6
        b += f'<path d="M{cx+(124-l)*math.cos(a):.1f} {cy+(124-l)*math.sin(a):.1f}L{cx+124*math.cos(a):.1f} {cy+124*math.sin(a):.1f}" stroke="#222" stroke-width="{3 if k%5==0 else 1.2}"/>'
    for k, t in enumerate(["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]):
        a = k * math.pi / 6 - math.pi / 2
        b += f'<text x="{cx+90*math.cos(a):.1f}" y="{cy+90*math.sin(a)+6:.1f}" text-anchor="middle" font-family="Cormorant Garamond,serif" font-weight="700" font-size="20" fill="#222">{t}</text>'
    b += f'<path d="M{cx} {cy}L{cx-40} {cy-60}" stroke="#222" stroke-width="7" stroke-linecap="round"/><path d="M{cx} {cy}L{cx+78} {cy+24}" stroke="#222" stroke-width="5" stroke-linecap="round"/><circle cx="{cx}" cy="{cy}" r="10" fill="var(--acc)"/>'
    # key (second key)
    b += '<g transform="translate(560 300) rotate(35)"><circle r="20" fill="none" stroke="url(#c5t)" stroke-width="7"/><rect x="18" y="-4" width="96" height="8" rx="2" fill="url(#c5t)"/><path d="M88 4h10v18h-10zM106 4h8v13h-8z" fill="url(#c5t)"/></g>'
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 6 Poisoned Invitation
def c6():
    n = 6; r = random.Random(66)
    defs = '''<radialGradient id="c6g" cx=".5" cy=".4" r=".65"><stop offset="0" stop-color="var(--acc2)" stop-opacity=".5"/><stop offset="1" stop-color="var(--bg)" stop-opacity="0"/></radialGradient>
<linearGradient id="c6w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c0304f"/><stop offset="1" stop-color="#5c0d25"/></linearGradient>'''
    b = '<rect width="800" height="520" fill="var(--bg)"/><rect width="800" height="520" fill="url(#c6g)"/>'
    for i in range(7):
        b += f'<path d="M{i*130-20} 0q40 60 0 120q-40 60 0 120" fill="none" stroke="var(--acc)" stroke-opacity=".08" stroke-width="2"/>'
    # table
    b += '<path d="M0 400H800V520H0Z" fill="var(--bg2)"/><path d="M0 400H800" stroke="var(--acc)" stroke-opacity=".6" stroke-width="2"/><path d="M0 440H800M0 480H800" stroke="var(--acc)" stroke-opacity=".12"/>'
    # candelabra left
    b += '<g transform="translate(140 400)"><rect x="-4" y="-170" width="8" height="170" fill="var(--acc)"/><path d="M-60 -120q0 40 60 40q60 0 60 -40" fill="none" stroke="var(--acc)" stroke-width="6"/><rect x="-30" y="-8" width="60" height="8" fill="var(--acc)"/>' + ''.join(f'<rect x="{x-5}" y="{y-34}" width="10" height="34" fill="#efe3cc"/><path d="M{x} {y-34}q-9 -18 0 -36q9 18 0 36Z" fill="#ffd27a"/><circle cx="{x}" cy="{y-52}" r="42" fill="#ffd27a" opacity=".12"/>' for x, y in ((-60, -118), (0, -170), (60, -118))) + '</g>'
    # invitation card
    b += '<g transform="translate(400 240) rotate(4)"><rect x="-118" y="-170" width="236" height="320" fill="var(--paper)" stroke="var(--acc2)" stroke-width="3"/><rect x="-104" y="-156" width="208" height="292" fill="none" stroke="var(--bg)" stroke-opacity=".6" stroke-width="1.5"/><rect x="-96" y="-148" width="192" height="276" fill="none" stroke="var(--acc2)" stroke-opacity=".7"/>'
    b += '<path d="M-60 -100q60 -34 120 0" fill="none" stroke="var(--bg)" stroke-opacity=".7" stroke-width="2"/><rect x="-62" y="-70" width="124" height="6" fill="var(--bg)" opacity=".6"/><rect x="-44" y="-52" width="88" height="4" fill="var(--bg)" opacity=".4"/>' + ''.join(f'<rect x="-70" y="{-14+i*18}" width="{140-(i*23)%36}" height="3" fill="var(--bg)" opacity=".35"/>' for i in range(5))
    b += '<circle cx="0" cy="92" r="28" fill="url(#c6w)"/><circle cx="0" cy="92" r="20" fill="none" stroke="#00000055" stroke-width="2"/><path d="M-8 92l8 -9 8 9 -8 9Z" fill="#00000050"/></g>'
    # goblet right
    b += '<g transform="translate(640 400)"><path d="M-44 -150h88q4 70 -44 88q-48 -18 -44 -88Z" fill="var(--acc)" opacity=".25" stroke="var(--acc)" stroke-width="3"/><path d="M-41 -118h82q-3 44 -41 58q-38 -14 -41 -58Z" fill="url(#c6w)"/><path d="M0 -62V-8M-30 0h60" stroke="var(--acc)" stroke-width="5" fill="none"/><ellipse cx="0" cy="0" rx="34" ry="6" fill="var(--acc)"/><path d="M-30 -110q-4 30 8 46" stroke="#fff" stroke-opacity=".4" stroke-width="3" fill="none"/><path d="M0 -204q-9 18 0 30q9 -12 0 -30Z" fill="#8cf0b4"/><ellipse cx="0" cy="-118" rx="41" ry="5" fill="none" stroke="#fff" stroke-opacity=".35"/></g>'
    # plate + fork
    b += '<ellipse cx="270" cy="470" rx="90" ry="20" fill="var(--acc)" opacity=".18" stroke="var(--acc)" stroke-opacity=".6"/><path d="M380 450v50M392 450v50M404 450v50M380 450q12 14 24 0M392 498h0" stroke="var(--acc)" stroke-opacity=".6" stroke-width="3"/>'
    for _ in range(12):
        b += sparkle(r.randint(30, 770), r.randint(30, 330), r.choice([4, 6, 8]), "var(--acc)", r.choice([.3, .5, .8]))
    return wrap(n, b, defs)

# ------------------------------------------------------------------ 7 Final Deception
def c7():
    n = 7; r = random.Random(77)
    defs = '''<radialGradient id="c7g" cx=".5" cy=".5" r=".6"><stop offset="0" stop-color="var(--acc)" stop-opacity=".28"/><stop offset="1" stop-color="var(--bg)" stop-opacity="0"/></radialGradient>
<linearGradient id="c7m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ececf2"/><stop offset="1" stop-color="#8b8c96"/></linearGradient>'''
    b = '<rect width="800" height="520" fill="var(--bg)"/><rect width="800" height="520" fill="url(#c7g)"/>'
    cx, cy = 400, 262
    for i in range(1, 6):
        b += f'<circle cx="{cx}" cy="{cy}" r="{i*52}" fill="none" stroke="var(--line)" stroke-opacity=".55" stroke-dasharray="3 7"/>'
    nodes = [(cx + 175 * math.cos(-math.pi / 2 + k * 2 * math.pi / 5), cy + 175 * math.sin(-math.pi / 2 + k * 2 * math.pi / 5)) for k in range(5)]
    for i, (x, y) in enumerate(nodes):
        x2, y2 = nodes[(i + 2) % 5]
        b += f'<path d="M{x:.0f} {y:.0f}L{x2:.0f} {y2:.0f}" stroke="var(--acc)" stroke-opacity=".55" stroke-width="1.6"/>'
    for (x, y) in nodes:
        mx, my = (cx + x) / 2 + r.randint(-14, 14), (cy + y) / 2 + r.randint(-14, 14)
        b += f'<path d="M{cx} {cy}Q{mx:.0f} {my:.0f} {x:.0f} {y:.0f}" stroke="var(--acc)" stroke-width="2.6" fill="none"/>'
    for i, (x, y) in enumerate(nodes):
        b += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="34" fill="var(--bg2)" stroke="var(--acc2)" stroke-width="3"/><circle cx="{x:.0f}" cy="{y-6:.0f}" r="12" fill="var(--acc2)" opacity=".85"/><path d="M{x-20:.0f} {y+22:.0f}q20 -26 40 0Z" fill="var(--acc2)" opacity=".85"/><circle cx="{x:.0f}" cy="{y-34:.0f}" r="6" fill="#e2c777"/>'
    # mask
    b += f'<g transform="translate({cx} {cy})"><path d="M-92 -26Q-70 -64 0 -58Q70 -64 92 -26Q98 22 60 38Q34 46 20 22Q0 8 -20 22Q-34 46 -60 38Q-98 22 -92 -26Z" fill="url(#c7m)" stroke="#00000066" stroke-width="2"/><path d="M-70 -8Q-48 -26 -24 -6Q-46 16 -70 -8Z M70 -8Q48 -26 24 -6Q46 16 70 -8Z" fill="var(--bg)"/><path d="M-84 -34Q0 -78 84 -34" stroke="var(--acc)" stroke-width="4" fill="none"/><path d="M0 -58V-86M-12 -80L0 -96L12 -80" stroke="#e2c777" stroke-width="3" fill="none"/><circle cx="0" cy="-60" r="5" fill="var(--acc)"/></g>'
    for i, (t, x, y) in enumerate((("I", 60, 190), ("II", 60, 245), ("III", 60, 300))):
        b += f'<g transform="translate({x} {y})"><path d="M0 0h54l10 14l-10 14h-54z" fill="#e2c777"/><circle cx="8" cy="14" r="3" fill="var(--bg)"/><text x="32" y="20" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-weight="600" font-size="14" fill="#1b1b1b">{t}</text></g>'
    return wrap(n, b, defs)

# ------------------------------------------------------------------ Hero (landing)
def hero():
    r = random.Random(5)
    defs = '''<linearGradient id="hs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07080d"/><stop offset=".6" stop-color="#141826"/><stop offset="1" stop-color="#2a2630"/></linearGradient>
<radialGradient id="hm" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#e9e4d4" stop-opacity=".5"/><stop offset="1" stop-color="#e9e4d4" stop-opacity="0"/></radialGradient>
<radialGradient id="hl" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffd890" stop-opacity=".95"/><stop offset=".25" stop-color="#ffc060" stop-opacity=".35"/><stop offset="1" stop-color="#ffc060" stop-opacity="0"/></radialGradient>
<linearGradient id="hf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9aa3b8" stop-opacity="0"/><stop offset="1" stop-color="#9aa3b8" stop-opacity=".35"/></linearGradient>
<filter id="hb"><feGaussianBlur stdDeviation="14"/></filter><filter id="hb2"><feGaussianBlur stdDeviation="3"/></filter>'''
    b = '<rect width="1600" height="900" fill="url(#hs)"/>'
    for _ in range(90):
        b += f'<circle cx="{r.randint(0,1600)}" cy="{r.randint(0,420)}" r="{r.choice([.7,1,1.4])}" fill="#fff" opacity="{r.choice([.2,.4,.7])}"/>'
    b += '<circle cx="1180" cy="190" r="190" fill="url(#hm)"/><circle cx="1180" cy="190" r="48" fill="#ece6d3"/><circle cx="1196" cy="180" r="48" fill="#0f1220" opacity=".0"/>'
    def skyline(y0, hmin, hmax, fill, seed, op):
        rr = random.Random(seed); x = -20; s = f'<g fill="{fill}" opacity="{op}">'
        while x < 1640:
            w = rr.randint(40, 110); h = rr.randint(hmin, hmax)
            s += f'<rect x="{x}" y="{y0-h}" width="{w}" height="{h+400}"/>'
            if rr.random() < .35: s += f'<path d="M{x+4} {y0-h}L{x+w/2} {y0-h-rr.randint(30,70)}L{x+w-4} {y0-h}Z"/>'
            if rr.random() < .25: s += f'<rect x="{x+w*0.4}" y="{y0-h-40}" width="6" height="40"/>'
            x += w + rr.randint(0, 14)
        return s + '</g>'
    b += skyline(640, 60, 200, "#161a29", 1, .9)
    # clock tower (generic gothic tower)
    b += '<g fill="#0d0f19"><rect x="260" y="150" width="74" height="500"/><rect x="250" y="250" width="94" height="14"/><path d="M256 150L297 40L338 150Z"/><rect x="293" y="14" width="8" height="30"/><rect x="236" y="400" width="122" height="250"/></g><circle cx="297" cy="212" r="26" fill="#e9d9a8" opacity=".95"/><circle cx="297" cy="212" r="26" fill="url(#hl)" opacity=".9"/><path d="M297 212V194M297 212L309 220" stroke="#2b2118" stroke-width="3" stroke-linecap="round"/>'
    b += skyline(700, 40, 150, "#0e1019", 2, 1)
    for _ in range(46):
        b += f'<rect x="{r.randint(0,1580)}" y="{r.randint(520,690)}" width="8" height="12" fill="#ffc874" opacity="{r.choice([.25,.5,.8])}"/>'
    # fog back
    b += '<g class="fog f1"><ellipse cx="500" cy="700" rx="700" ry="70" fill="#a9b1c4" opacity=".16" filter="url(#hb)"/><ellipse cx="1300" cy="720" rx="600" ry="60" fill="#a9b1c4" opacity=".14" filter="url(#hb)"/></g>'
    # street
    b += '<path d="M0 760H1600V900H0Z" fill="#0a0b11"/><path d="M0 760H1600" stroke="#2b2f43" stroke-width="2"/>'
    for i in range(14):
        y = 775 + i * 9
        b += f'<path d="M0 {y}H1600" stroke="#1a1d2b" stroke-width="1" opacity="{.8-i*.04:.2f}"/>'
    b += '<ellipse cx="1150" cy="830" rx="150" ry="22" fill="#ffc060" opacity=".16"/>'
    # lamp
    b += '<g><rect x="1146" y="420" width="10" height="340" fill="#07080c"/><rect x="1130" y="740" width="42" height="22" fill="#07080c"/><path d="M1126 420h50l-8 -34h-34z" fill="#07080c"/><rect x="1136" y="372" width="30" height="48" fill="#ffd890"/><path d="M1130 372h42l-21 -22z" fill="#07080c"/></g><circle cx="1151" cy="398" r="210" fill="url(#hl)" class="flick"/>'
    # window lit house
    b += '<g><rect x="1330" y="520" width="240" height="250" fill="#0b0d16"/><rect x="1362" y="568" width="64" height="86" fill="#ffc874" opacity=".9"/><path d="M1394 568V654M1362 611H1426" stroke="#0b0d16" stroke-width="3"/><rect x="1470" y="568" width="64" height="86" fill="#ffc874" opacity=".35"/></g>'
    # detective silhouette (generic: long coat, bowler, umbrella, seen from behind)
    b += '<g transform="translate(980 560)"><ellipse cx="22" cy="206" rx="64" ry="9" fill="#000" opacity=".5"/><path d="M-6 60Q-20 120 -24 200H66Q64 120 50 60Q22 46 -6 60Z" fill="#090a10"/><path d="M-4 62Q22 76 48 62L44 40Q22 30 0 40Z" fill="#090a10"/><circle cx="22" cy="18" r="21" fill="#090a10"/><path d="M-6 8H50V0Q50 -22 22 -22Q-6 -22 -6 0Z" fill="#05060a"/><rect x="-14" y="4" width="72" height="7" rx="3" fill="#05060a"/><path d="M56 70L78 170" stroke="#090a10" stroke-width="7" stroke-linecap="round"/><path d="M78 170L84 206" stroke="#090a10" stroke-width="5"/><path d="M60 80Q82 60 70 100" fill="none" stroke="#090a10" stroke-width="4"/><path d="M-12 60L-6 70" stroke="#c8283a" stroke-width="2"/></g>'
    # red thread
    b += '<path class="thread" d="M1064 636C1000 700 880 640 760 700C620 770 560 640 470 690C380 740 330 680 300 726" fill="none" stroke="#e0364a" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1400" stroke-dashoffset="0"/><circle cx="300" cy="726" r="6" fill="#e0364a"/>'
    b += '<g class="fog f2"><ellipse cx="900" cy="800" rx="900" ry="70" fill="#b4bcd0" opacity=".16" filter="url(#hb)"/></g>'
    return wrap("hero", b, defs).replace('viewBox="0 0 800 520"', 'viewBox="0 0 1600 900"').replace('preserveAspectRatio="xMidYMid slice"', 'preserveAspectRatio="xMidYMax slice"')

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for i, f in enumerate((c1, c2, c3, c4, c5, c6, c7), 1):
        open(os.path.join(OUT, f"cover_{i}.html"), "w").write(f())
    open(os.path.join(OUT, "hero.html"), "w").write(hero())
    print("ok", os.listdir(OUT))
