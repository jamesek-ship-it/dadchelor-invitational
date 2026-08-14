#!/usr/bin/env python3
"""
Dadchelor consistency checker.
Verifies the three copies of tournament truth agree:
  1. MATCHES array   (drives scoring / leaderboard)
  2. Draw page HTML  (what players see)
  3. Admin labels    (what the commissioner clicks)
Also checks point totals, div balance, and JS syntax.
Run before EVERY push:  python3 verify.py
"""
import re, sys, subprocess

FAIL = []
def check(ok, msg):
    print(("  OK   " if ok else " FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)

h = open('dadchelor_v2.html').read()
sur = lambda s: '/'.join(x.strip().split()[-1] for x in s.split(',') if x.strip())
unspace = lambda s: s.replace(', ', ',')

# ---------- 1. MATCHES (ALL copies must agree) ----------
arrays = []
for am in re.finditer(r'var MATCHES\s*=', h):
    p0 = am.start(); seg = h[p0:h.find('];', p0) + 2]
    d = {}
    for m in re.finditer(r"\{\s*id:'(\w+)',(?:\s*round:\d+,)?\s*look:\[(.*?)\],\s*feel:\[(.*?)\],\s*pts:(\d)", seg):
        clean = lambda x: ','.join(y.strip() for y in x.replace("'", "").split(','))
        d[m.group(1)] = (clean(m.group(2)), clean(m.group(3)), int(m.group(4)))
    arrays.append((p0, d))
print(f"\nMATCHES arrays found: {len(arrays)}")
base = arrays[0][1]
for pos, d in arrays[1:]:
    play = {k: v for k, v in d.items() if not k.endswith(('ctp', 'ld'))}
    bplay = {k: v for k, v in base.items() if not k.endswith(('ctp', 'ld'))}
    check(set(play) == set(bplay), f"MATCHES@{pos} has same match ids as MATCHES@{arrays[0][0]}")
    for k in sorted(set(play) & set(bplay)):
        check(play[k] == bplay[k], f"MATCHES@{pos} {k} identical")
M = {k: v for k, v in base.items() if not k.endswith(('ctp', 'ld'))}
print(f"canonical: {len(M)} matches")

# ---------- 2. Draw page ----------
ds = h.find('id="page-draw"'); de = h.find('<script>', ds); draw = h[ds:de]
drawn = []
for rnd in ['Round 1', 'Round 2', 'Round 3']:
    i = draw.find('>' + rnd + '<'); j = draw.find('>Round', i + 10)
    blk = draw[i:j if j > i else len(draw)]
    t = [re.sub(r'<[^>]+>', '', re.sub(r'<br>', ',', mm.group(2))).replace('(C)', '').replace('(A)', '').strip()
         for mm in re.finditer(r'class="match-team (look|feel)"[^>]*>(.*?)</div>', blk, re.DOTALL)]
    for k in range(0, len(t) - 1, 2):
        drawn.append((t[k], t[k + 1]))

# ---------- 3. Admin labels ----------
ai = h.find('id="page-admin"'); aj = h.find('<script>', ai); adm = h[ai:aj]
admin = re.findall(r'admin-match-name look">([^<]*)</span>.*?data-match="(\w+)".*?admin-match-name feel">([^<]*)</span>',
                   adm, re.DOTALL)

print("\n=== Draw page vs MATCHES ===")
norm = lambda s: ','.join(sorted(x.strip() for x in s.replace('  ',' ').split(',') if x.strip()))
ids = [k for k in M if not k.startswith('r4')]
check(len(drawn) == len(ids), f"draw shows {len(drawn)} matches, MATCHES has {len(ids)}")
for k, mid in enumerate(ids):
    if k >= len(drawn): break
    dl, df = drawn[k]; ml, mf, _ = M[mid]
    check(norm(dl) == norm(ml) and norm(df) == norm(mf),
          f"{mid}: {sur(dl)} vs {sur(df)}")

print("\n=== Admin labels vs MATCHES ===")
for lk, mid, fl in admin:
    if mid not in M:
        check(False, f"{mid} in admin but not MATCHES"); continue
    el, ef = sur(M[mid][0]), sur(M[mid][1])
    gl = re.sub(r'[^A-Za-z/]', '', lk); gf = re.sub(r'[^A-Za-z/]', '', fl)
    check(gl == el.replace(' ', '') and gf.startswith(ef.replace(' ', '')),
          f"{mid}: {lk.strip()} vs {fl.strip()}")

print("\n=== Point totals ===")
mp = sum(v[2] for v in M.values())
check(mp == 15, f"match points = {mp} (expect 15)")
rows = re.findall(r'<span>([^<]+)</span><span class="pts-val[^"]*">(\d+)</span>', h)
tbl = {a: int(b) for a, b in rows}
s = sum(v for k, v in tbl.items() if k != 'Total')
check(s == 19, f"Points Available rows sum = {s} (expect 19)")
check(tbl.get('Total') == 19 or 'Total' not in tbl, f"Points Available total = {tbl.get('Total')}")
check(h.count("textContent = 'of 19'") == 1, "leaderboard denominator = 19")

print("\n=== Structure ===")
body = re.sub(r'<style>.*?</style>', '', re.sub(r'<script>.*?</script>', '', h, flags=re.DOTALL), flags=re.DOTALL)
bal = len(re.findall(r'<div\b', body)) - len(re.findall(r'</div>', body))
check(bal == -1, f"div balance = {bal} (expect -1)")
check(open('index.html').read() == h, "index.html identical to dadchelor_v2.html")

print("\n=== JS syntax ===")
bad = 0
for n, b in enumerate(re.findall(r'<script>(.*?)</script>', h, re.DOTALL)):
    open(f'/tmp/_v{n}.js', 'w').write(b)
    if subprocess.run(['node', '--check', f'/tmp/_v{n}.js'], capture_output=True).returncode:
        bad += 1
check(bad == 0, f"{bad} script blocks with syntax errors")

# ---------- 6. Duplicate definitions (this bug has bitten 3x) ----------
print("\n=== Duplicate definitions ===")
js = '\n'.join(re.findall(r'<script>(.*?)</script>', h, re.DOTALL))
from collections import Counter
fn = Counter(re.findall(r'(?m)^function\s+([A-Za-z_$][\w$]*)\s*\(', js))
dupfn = {k: v for k, v in fn.items() if v > 1}
check(not dupfn, f"no duplicate GLOBAL function declarations {dupfn if dupfn else ''}")
win = Counter(re.findall(r'\bwindow\.([A-Za-z_$][\w$]*)\s*=\s*function', js))
dupwin = {k: v for k, v in win.items() if v > 1}
check(not dupwin, f"no duplicate window.* assignments {dupwin if dupwin else ''}")
blocks = [b.strip() for b in re.findall(r'<script>(.*?)</script>', h, re.DOTALL)]
bc = Counter(blocks)
check(not [b for b, n in bc.items() if n > 1], "no verbatim-duplicate script blocks")

# ---------- 7. Duplicate element IDs ----------
ids = re.findall(r'\sid="([^"]+)"', re.sub(r'<script>.*?</script>', '', h, flags=re.DOTALL))
dupids = {k: v for k, v in Counter(ids).items() if v > 1}
check(not dupids, f"no duplicate element ids {dupids if dupids else ''}")

# ---------- 8. Roster integrity ----------
print("\n=== Roster integrity ===")
rm = re.search(r'const ROSTER_2026\s*=\s*\{(.*?)\n\};', h, re.DOTALL)
roster = {'look': [], 'feel': []}
if rm:
    for side in ('look', 'feel'):
        sm = re.search(side + r':\s*\[(.*?)\]', rm.group(1), re.DOTALL)
        if sm:
            roster[side] = re.findall(r"name:'([^']+)'", sm.group(1))
check(len(roster['look']) == 6, f"Look Good roster = {len(roster['look'])} (expect 6)")
check(len(roster['feel']) == 6, f"Feel Good roster = {len(roster['feel'])} (expect 6)")
caps = re.findall(r"name:'([^']+)',\s*role:'C'", h)
alts = re.findall(r"name:'([^']+)',\s*role:'a'", h)
check(len(caps) == 2, f"exactly 2 Captains {caps}")
check(len(alts) <= 2, f"at most 2 Alternates {alts}")

players = set(re.findall(r'name:"([^"]+)"', h))
for side in ('look', 'feel'):
    for n in roster[side]:
        check(n in players, f"roster name in PLAYERS: {n}")

# every name used in a match must be on the right team
for mid, (lk, fl, pts) in sorted(M.items()):
    for n in [x for x in lk.split(',') if x]:
        check(n in roster['look'], f"{mid} look side: {n} is Look Good")
    for n in [x for x in fl.split(',') if x]:
        check(n in roster['feel'], f"{mid} feel side: {n} is Feel Good")

# no player double-booked inside one round
for rnd in ('r1', 'r2', 'r3'):
    seen = []
    for mid, (lk, fl, _) in M.items():
        if mid.startswith(rnd):
            seen += [x for x in (lk + ',' + fl).split(',') if x]
    dup = [k for k, v in Counter(seen).items() if v > 1]
    check(not dup, f"{rnd}: no player in two matches {dup if dup else ''}")

# ---------- 9. Portraits ----------
print("\n=== Portraits ===")
import os
im = re.search(r'const IMAGES\s*=\s*\{(.*?)\n\};', h, re.DOTALL)
keys = dict(re.findall(r'(\w+):\s*"([^"]+)"', im.group(1))) if im else {}
for k, path in keys.items():
    check(os.path.exists(path.lstrip('/')), f"portrait file exists: {path}")
for side in ('look', 'feel'):
    for n in roster[side]:
        km = re.search(r'name:"' + re.escape(n) + r'"[^}]*?key:"(\w+)"', h)
        check(bool(km) and km.group(1) in keys, f"{n} has a portrait")

# ---------- 10. Leftovers ----------
print("\n=== Leftovers ===")
for bad_str in ["Add the champion's quote", "lorem", "TODO", "FIXME"]:
    check(bad_str not in h, f"no '{bad_str}' in file")
check(h.count('localStorage') <= 6, "localStorage use stays minimal and guarded")
check(h.count('localStorage') == 0 or 'try { window.localStorage' in h or 'try { me = window.localStorage' in h,
      "localStorage calls are wrapped in try/catch")
check('Bronze Chalice' not in h, "no stale 'Bronze Chalice'")

# ---------- 11. Service worker ----------
print("\n=== Service worker ===")
if os.path.exists('sw.js'):
    sw = open('sw.js').read()
    check(subprocess.run(['node', '--check', 'sw.js'], capture_output=True).returncode == 0, "sw.js syntax")
    check('dadchelor-invitational/' not in sw, "sw.js has no stale subdirectory paths")

print("\n" + ("=" * 46))
if FAIL:
    print(f"FAILED — {len(FAIL)} problem(s). DO NOT PUSH.")
    for f in FAIL: print("   -", f)
    sys.exit(1)
print("ALL CHECKS PASSED — safe to push")
