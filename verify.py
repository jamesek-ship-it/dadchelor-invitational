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

print("\n" + ("=" * 46))
if FAIL:
    print(f"FAILED — {len(FAIL)} problem(s). DO NOT PUSH.")
    for f in FAIL: print("   -", f)
    sys.exit(1)
print("ALL CHECKS PASSED — safe to push")
