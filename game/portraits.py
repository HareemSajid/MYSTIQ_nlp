"""Procedural engraved-style portraits. Deterministic from suspect key/name/age/gender/public role only
(no case-solution information), so a portrait can never hint at guilt."""
import hashlib

SKIN = ["#f0d3b4", "#e6c29c", "#d9ae85", "#c4916a", "#a87454", "#8a5a3e"]
HAIR = ["#1d1713", "#32231a", "#55391f", "#7a5231", "#a07a46", "#c3a46a", "#6b2f1c"]


def _pick(h, shift, seq):
    return seq[(h >> shift) % len(seq)]


def build(s, size=120):
    h = int(hashlib.md5(f"{s.key}|{s.name}".encode()).hexdigest(), 16)
    fem = s.gender == "f"
    age = s.age or 40
    role = (s.role or "").lower()
    skin = _pick(h, 2, SKIN[:4] if (h >> 40) % 5 else SKIN)
    sd = {"#f0d3b4": "#c99c78", "#e6c29c": "#b98a64", "#d9ae85": "#a97a54", "#c4916a": "#92623f", "#a87454": "#7a4a2f", "#8a5a3e": "#63381f"}[skin]
    grey = age >= 52
    hair = "#b9b5ae" if grey else _pick(h, 8, HAIR)
    if 44 <= age < 52 and (h >> 12) % 2:
        hair = "#8b8680"
    uid = f"p{h % 99999}"
    worker = any(k in role for k in ("maintenance", "apprentice", "guard", "railway", "worker"))
    guard = "guard" in role or "railway" in role
    scholar = any(k in role for k in ("scholar", "historian", "librarian", "journalist"))
    maid = fem and any(k in role for k in ("assistant", "secretary", "household"))
    lady = fem and not maid
    o = []
    # background
    o.append(f'<defs><radialGradient id="{uid}b" cx=".5" cy=".38" r=".75"><stop offset="0" stop-color="var(--acc)" stop-opacity=".42"/><stop offset=".6" stop-color="var(--surf2)"/><stop offset="1" stop-color="var(--bg)"/></radialGradient>'
             f'<linearGradient id="{uid}f" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{sd}" stop-opacity=".75"/><stop offset=".45" stop-color="{skin}" stop-opacity="0"/><stop offset="1" stop-color="{sd}" stop-opacity=".25"/></linearGradient>'
             f'<pattern id="{uid}h" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><rect width="4" height="1.1" fill="#000" opacity=".16"/></pattern>'
             f'<clipPath id="{uid}c"><rect width="200" height="240" rx="3"/></clipPath></defs>')
    o.append(f'<g clip-path="url(#{uid}c)"><rect width="200" height="240" fill="url(#{uid}b)"/>')
    # long-hair back layer (women)
    if fem:
        o.append(f'<path d="M48 96Q44 40 100 36Q156 40 152 96Q158 140 142 160L128 120L72 120L58 160Q42 140 48 96Z" fill="{hair}"/>')
    # coat / shoulders
    coat = _pick(h, 14, ["#23262d", "#2c2622", "#2a3140", "#33291f", "#27302b"])
    if lady:
        coat = _pick(h, 14, ["#4a2a3a", "#2e3a52", "#3d4a3a", "#52382a", "#2a2a38"])
    if maid:
        coat = "#26262b"
    o.append(f'<path d="M-6 250Q-2 196 54 180L84 170H116L146 180Q202 196 206 250Z" fill="{coat}"/>')
    o.append(f'<path d="M-6 250Q-2 196 54 180L84 170H116L146 180Q202 196 206 250Z" fill="url(#{uid}h)"/>')
    # neck
    o.append(f'<path d="M82 150H118V182Q100 196 82 182Z" fill="{skin}"/><path d="M82 150H118V166Q100 176 82 166Z" fill="{sd}" opacity=".55"/>')
    # shirt / collar / cravat
    if fem:
        o.append('<path d="M72 178Q100 206 128 178L132 200Q100 226 68 200Z" fill="#eee7d8"/><path d="M80 182Q100 198 120 182" stroke="#b9ad92" stroke-width="2" fill="none"/>')
        if maid:
            o.append('<path d="M60 196Q100 232 140 196L146 214Q100 250 54 214Z" fill="#f4efe2"/>')
        else:
            o.append(f'<circle cx="100" cy="200" r="5" fill="var(--acc2)"/><path d="M76 186Q100 214 124 186" stroke="#d9cdb0" stroke-width="3" fill="none" stroke-dasharray="2 3"/>')
    else:
        o.append('<path d="M78 172L100 204L122 172L128 190L100 230L72 190Z" fill="#efe9db"/>')
        o.append('<path d="M70 168L84 176L80 192L66 182Z M130 168L116 176L120 192L134 182Z" fill="#f6f1e4"/>')
        k = (h >> 18) % 3
        if k == 0:
            o.append('<path d="M92 190L100 198L108 190L112 204L100 210L88 204Z" fill="var(--acc2)"/>')
        elif k == 1:
            o.append('<path d="M96 188H104L108 232H92Z" fill="#6b1f2b"/><circle cx="100" cy="196" r="4" fill="#6b1f2b"/>')
        else:
            o.append('<path d="M84 186L100 200L116 186L112 210H88Z" fill="#3d3a46"/>')
        if worker and not guard:
            o.append('<path d="M82 176Q100 192 118 176L122 190Q100 206 78 190Z" fill="#8a2f2a"/>')
        if guard:
            o.append('<rect x="95" y="205" width="10" height="9" rx="2" fill="var(--acc2)"/><circle cx="82" cy="222" r="3.4" fill="var(--acc2)"/><circle cx="118" cy="222" r="3.4" fill="var(--acc2)"/>')
        else:
            o.append('<path d="M72 206Q100 222 128 206L136 250H64Z" fill="#14161a" opacity=".6"/>')
            o.append('<circle cx="100" cy="224" r="3" fill="var(--acc2)"/>')
    # ears
    o.append(f'<ellipse cx="55" cy="108" rx="7" ry="12" fill="{skin}"/><ellipse cx="145" cy="108" rx="7" ry="12" fill="{skin}"/><ellipse cx="55" cy="108" rx="3" ry="7" fill="{sd}" opacity=".5"/><ellipse cx="145" cy="108" rx="3" ry="7" fill="{sd}" opacity=".5"/>')
    # face
    jaw = 40 + (h >> 20) % 8 if not fem else 36 + (h >> 20) % 5
    o.append(f'<path d="M58 92Q56 58 100 56Q144 58 142 92Q144 132 124 148Q112 160 100 160Q88 160 76 148Q56 132 58 92Z" fill="{skin}"/>')
    o.append(f'<path d="M58 92Q56 58 100 56Q144 58 142 92Q144 132 124 148Q112 160 100 160Q88 160 76 148Q56 132 58 92Z" fill="url(#{uid}f)"/>')
    # cheek/jaw shade
    o.append(f'<path d="M62 118Q70 146 92 156Q74 156 66 134Z" fill="{sd}" opacity=".35"/><path d="M138 118Q130 146 108 156Q126 156 134 134Z" fill="{sd}" opacity=".25"/>')
    # age lines
    if age >= 40:
        o.append(f'<path d="M72 78Q100 72 128 78M76 84Q100 79 124 84" stroke="{sd}" stroke-width="1.4" fill="none" opacity=".5"/>')
        o.append(f'<path d="M80 120Q76 128 80 136M120 120Q124 128 120 136" stroke="{sd}" stroke-width="1.3" fill="none" opacity=".55"/>')
    if age >= 52:
        o.append(f'<path d="M70 104q-6 4 -8 10M130 104q6 4 8 10" stroke="{sd}" stroke-width="1.2" fill="none" opacity=".55"/>')
    # brows
    bt = 3.2 if not fem else 2.0
    bc = hair if not grey else "#8f8a84"
    ang = (h >> 25) % 3 - 1
    o.append(f'<path d="M71 {93+ang}Q82 {86}93 {91}" stroke="{bc}" stroke-width="{bt}" stroke-linecap="round" fill="none"/><path d="M107 91Q118 {86}129 {93+ang}" stroke="{bc}" stroke-width="{bt}" stroke-linecap="round" fill="none"/>')
    # eyes
    o.append(f'<path d="M73 101Q82 95 91 101Q82 106 73 101Z" fill="#f4f0e6"/><path d="M109 101Q118 95 127 101Q118 106 109 101Z" fill="#f4f0e6"/>')
    ic = _pick(h, 30, ["#3a2a1c", "#4a6a7a", "#5a6a3a", "#2a2018", "#5a4a30"])
    o.append(f'<circle cx="82" cy="100.5" r="3.6" fill="{ic}"/><circle cx="118" cy="100.5" r="3.6" fill="{ic}"/><circle cx="82" cy="100.5" r="1.5" fill="#0c0a08"/><circle cx="118" cy="100.5" r="1.5" fill="#0c0a08"/><circle cx="83.2" cy="99.3" r="1" fill="#fff" opacity=".85"/><circle cx="119.2" cy="99.3" r="1" fill="#fff" opacity=".85"/>')
    o.append(f'<path d="M72 100Q82 93 92 100M108 100Q118 93 128 100" stroke="#2a1c14" stroke-width="1.6" fill="none"/><path d="M74 105Q82 108 90 105M110 105Q118 108 126 105" stroke="{sd}" stroke-width="1.2" fill="none" opacity=".7"/>')
    # nose
    nl = 18 + (h >> 33) % 6
    o.append(f'<path d="M100 98Q97 {112}96 {98+nl}Q100 {104+nl}104 {98+nl}Q103 112 100 98Z" fill="{sd}" opacity=".35"/><path d="M94 {100+nl}Q100 {106+nl}106 {100+nl}" stroke="{sd}" stroke-width="2" fill="none" opacity=".8"/><path d="M104 100Q108 {112}106 {98+nl}" stroke="#fff" stroke-opacity=".18" stroke-width="2" fill="none"/>')
    # mouth
    my = 134
    lip = "#a4524a" if fem else "#9a5a4a"
    sm = (h >> 36) % 3
    o.append(f'<path d="M86 {my}Q100 {my+(3 if sm==0 else 1)}114 {my}" stroke="#5a2a22" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M88 {my}Q100 {my-5}112 {my}Q100 {my+1}88 {my}Z" fill="{lip}" opacity="{.9 if fem else .55}"/><path d="M90 {my+1}Q100 {my+9}110 {my+1}Q100 {my+4}90 {my+1}Z" fill="{lip}" opacity=".75"/>')
    # facial hair (men)
    if not fem:
        fh = (h >> 4) % 6
        fc = hair
        if fh in (0, 3):    # walrus / handlebar moustache
            o.append(f'<path d="M80 {my-6}Q92 {my-14}100 {my-8}Q108 {my-14}120 {my-6}Q112 {my+2}100 {my-2}Q88 {my+2}80 {my-6}Z" fill="{fc}"/>')
            if fh == 3:
                o.append(f'<path d="M80 {my-6}Q72 {my-4}70 {my-12}M120 {my-6}Q128 {my-4}130 {my-12}" stroke="{fc}" stroke-width="3" fill="none" stroke-linecap="round"/>')
        elif fh == 1:       # mutton chops + moustache
            o.append(f'<path d="M58 92Q60 128 74 146L82 132Q70 116 70 92Z M142 92Q140 128 126 146L118 132Q130 116 130 92Z" fill="{fc}"/><path d="M84 {my-6}Q100 {my-12}116 {my-6}Q100 {my-1}84 {my-6}Z" fill="{fc}"/>')
        elif fh == 2:       # full beard
            o.append(f'<path d="M58 100Q56 150 100 172Q144 150 142 100Q136 130 118 136Q100 128 82 136Q64 130 58 100Z" fill="{fc}"/><path d="M82 {my-6}Q100 {my-14}118 {my-6}Q100 {my-1}82 {my-6}Z" fill="{fc}"/><path d="M90 {my+1}Q100 {my+8}110 {my+1}Q100 {my+3}90 {my+1}Z" fill="{lip}"/>')
        elif fh == 4:       # goatee
            o.append(f'<path d="M88 {my+8}Q100 {my+4}112 {my+8}Q110 {my+26}100 {my+30}Q90 {my+26}88 {my+8}Z" fill="{fc}"/><path d="M86 {my-4}Q100 {my-10}114 {my-4}Q100 {my}86 {my-4}Z" fill="{fc}"/>')
        # fh == 5 clean shaven
        if fh == 5:
            o.append(f'<path d="M66 118Q70 144 100 156Q130 144 134 118Q120 148 100 148Q80 148 66 118Z" fill="{sd}" opacity=".18"/>')
    # hair
    if fem:
        sty = (h >> 10) % 3
        o.append(f'<path d="M56 98Q50 46 100 40Q150 46 144 98Q132 66 100 64Q68 66 56 98Z" fill="{hair}"/>')
        if sty == 0:
            o.append(f'<ellipse cx="100" cy="30" rx="26" ry="18" fill="{hair}"/><path d="M80 34Q100 22 120 34" stroke="#00000040" stroke-width="2" fill="none"/>')
        elif sty == 1:
            o.append(f'<path d="M58 96Q54 126 64 150Q50 128 56 98Z M142 96Q146 126 136 150Q150 128 144 98Z" fill="{hair}"/><path d="M62 52Q100 24 138 52Q100 36 62 52Z" fill="{hair}"/><circle cx="62" cy="130" r="9" fill="{hair}"/><circle cx="138" cy="130" r="9" fill="{hair}"/>')
        else:
            o.append(f'<path d="M60 70Q100 30 140 70Q100 50 60 70Z" fill="{hair}"/><circle cx="100" cy="36" r="17" fill="{hair}"/><path d="M60 74Q56 112 66 128" stroke="{hair}" stroke-width="9" fill="none" stroke-linecap="round"/><path d="M140 74Q144 112 134 128" stroke="{hair}" stroke-width="9" fill="none" stroke-linecap="round"/>')
        if maid:
            o.append('<path d="M60 62Q100 22 140 62Q132 52 100 46Q68 52 60 62Z" fill="#f2ede0"/><path d="M62 60Q100 40 138 60" stroke="#cfc6ad" stroke-width="2" fill="none"/>')
        elif (h >> 48) % 2:
            o.append(f'<path d="M58 54Q100 14 142 54Q120 40 100 40Q80 40 58 54Z" fill="{coat}"/><path d="M124 40Q150 26 156 52Q140 44 124 40Z" fill="var(--acc2)"/>')
    else:
        sty = (h >> 10) % 4
        top = hat = None
        o.append(f'<path d="M57 96Q52 50 100 44Q148 50 143 96Q138 70 128 66Q100 56 72 66Q62 70 57 96Z" fill="{hair}"/>')
        if sty == 0:
            o.append(f'<path d="M62 70Q100 40 138 70Q110 52 62 70Z" fill="{hair}"/><path d="M96 48Q74 54 66 76" stroke="#00000030" stroke-width="2" fill="none"/>')
        elif sty == 1:
            o.append(f'<path d="M60 74Q64 52 100 46Q136 52 140 74Q116 58 88 60Q70 62 60 74Z" fill="{hair}"/>')
        elif sty == 2 and age > 40:   # receding
            o.append(f'<path d="M57 96Q52 70 62 64Q60 78 70 84Q64 70 76 62Q70 70 74 80Z" fill="{hair}"/><ellipse cx="100" cy="62" rx="36" ry="10" fill="{skin}" opacity=".5"/>')
        else:
            o.append(f'<circle cx="68" cy="66" r="12" fill="{hair}"/><circle cx="100" cy="52" r="15" fill="{hair}"/><circle cx="132" cy="66" r="12" fill="{hair}"/><circle cx="84" cy="56" r="12" fill="{hair}"/><circle cx="118" cy="56" r="12" fill="{hair}"/>')
        # headwear
        if guard:
            o.append('<path d="M52 66Q54 30 100 28Q146 30 148 66Z" fill="#1c2330"/><rect x="48" y="62" width="104" height="10" rx="3" fill="#10151f"/><path d="M52 72Q100 88 148 72" fill="#10151f"/><circle cx="100" cy="52" r="7" fill="var(--acc2)"/><rect x="50" y="60" width="100" height="3" fill="var(--acc2)" opacity=".8"/>')
        elif worker:
            o.append(f'<path d="M52 70Q56 40 100 38Q144 40 148 70Q100 60 52 70Z" fill="#4a3f36"/><path d="M52 70Q100 62 148 70L156 78Q100 70 44 78Z" fill="#2c2520"/><circle cx="100" cy="42" r="3" fill="#2c2520"/>')
        elif (h >> 52) % 4 == 0:
            o.append(f'<ellipse cx="100" cy="58" rx="62" ry="9" fill="#14120f"/><path d="M62 58Q64 8 100 8Q136 8 138 58Z" fill="#1a1713"/><rect x="62" y="44" width="76" height="9" fill="#3a1f26"/>')
        elif (h >> 52) % 4 == 1:
            o.append(f'<ellipse cx="100" cy="60" rx="52" ry="8" fill="#1d1a17"/><path d="M64 60Q66 24 100 22Q134 24 136 60Z" fill="#23201c"/><rect x="64" y="48" width="72" height="8" fill="#0f0e0c"/>')
    if scholar and not fem or (scholar and (h >> 5) % 2):
        o.append(f'<circle cx="82" cy="101" r="14" fill="#cfe3ee" fill-opacity=".12" stroke="#2b2418" stroke-width="2"/><circle cx="118" cy="101" r="14" fill="#cfe3ee" fill-opacity=".12" stroke="#2b2418" stroke-width="2"/><path d="M96 100Q100 96 104 100M68 98L58 94M132 98L142 94" stroke="#2b2418" stroke-width="2" fill="none"/>')
    # highlights + engraving
    o.append(f'<ellipse cx="86" cy="76" rx="22" ry="9" fill="#fff" opacity=".1"/><rect width="200" height="240" fill="url(#{uid}h)" opacity=".55"/>')
    o.append('<rect width="200" height="240" fill="none" stroke="var(--acc)" stroke-opacity=".0"/></g>')
    h_px = int(size * 1.2)
    return (f'<svg class="portrait" viewBox="0 0 200 240" width="{size}" height="{h_px}" role="img" aria-label="Illustrated portrait of {s.name}" '
            f'xmlns="http://www.w3.org/2000/svg">' + "".join(o) + "</svg>")
