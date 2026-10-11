"""Deep-fried skin check: flags baked textures that have been pushed too far (blown-out highlights, neon saturation,
crunchy over-sharpened contrast, crushed blacks), so a recolour or a baked reflection that glares is caught at build
time instead of in game.

    python3 skin_check.py [dir or png ...]     # report on these (default: every texture build_pack.py baked into pack/)
    import skin_check; skin_check.report(paths)  # build_pack.py runs it after baking; HCE_STRICT_SKINS=1 makes it fail

A baked skin is judged against the texture it was baked from (build_pack.py registers each pair: SKIN_PAIRS), since
deep frying is what a bake does to a texture: a source that is meant to be a flat bright colour stays fine. Each is
scored on what "deep fried" looks like, measured over its painted texels (fully transparent and flat-black padding
left out):
  * blown:  share of texels with a channel at 250+ (detail lost to white or a pure primary)
  * neon:   share of bright texels (value > 0.8) that are also near-fully saturated (saturation > 0.85)
  * crunch: high-frequency contrast (mean absolute Laplacian) per unit of the texture's own tonal range -- noise and
            edges sharpened up past what a painted game texture has
  * crush:  share of texels at 5 or below in every channel (shadow detail lost to black)
  * glare:  share of near-white texels: value 0.85 and up with little colour left (saturation under 0.4), where
            highlights and reflections wash the paint out (a bright, saturated gold or orange is paint, not glare)
  * lift:   mean value (brightness)
A bake fails when it raises one of these past PAIR_LIMITS over its source (crunch as a ratio). The limits sit just
above the worst of the pack's approved skins (Halo CE's painted skins, the ranks' recolours, the kit; neon is reported
but not judged: the red Hunters and the Grunts' oranges are meant to be loud), so a new bake has to look like them;
the Ranger's first steel helmet (glare +0.09, lift +0.19) is the case it was written for.
Textures that are meant to glow (energy blades, shields, lights, visors, the flag) are left out.
"""
import os, sys, json
import numpy as np
from PIL import Image

LIMITS = dict(blown=0.08, neon=0.30, crunch=0.55, crush=0.35)          # a texture on its own (no source)
PAIR_LIMITS = dict(blown=0.25, crunch=2.2, crush=0.03, glare=0.12, lift=0.16)    # a bake against its source
SKIP = ('blade', 'shield', 'visor', 'lens', 'flag', 'light', 'glow', 'illum', 'hidden', 'brightmap', 'cube', 'gore_',
        'blood', 'camo', 'flame', 'exhaust', 'muzzle', 'hce_noblood', 'eyes', 'teeth', 'sword')


def metrics(path):
    im = Image.open(path)
    a = np.asarray(im.convert('RGBA'), np.float32)
    rgb = a[..., :3]; alpha = a[..., 3]
    painted = (alpha > 8) & (rgb.max(axis=2) > 2)
    if painted.sum() < 64: return None
    px = rgb[painted]
    mx = px.max(axis=1); mn = px.min(axis=1)
    v = mx / 255.0; sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    blown = float((mx >= 250).mean())
    bright = v > 0.8
    neon = float(((sat > 0.85) & bright).sum() / max(bright.sum(), 1)) if bright.sum() > 32 else 0.0
    crush = float((mx <= 5).mean())
    glare = float(((v >= 0.85) & (sat < 0.4)).mean()); lift = float(v.mean())
    lum = rgb.mean(axis=2)
    lap = np.abs(4 * lum[1:-1, 1:-1] - lum[:-2, 1:-1] - lum[2:, 1:-1] - lum[1:-1, :-2] - lum[1:-1, 2:])
    m = painted[1:-1, 1:-1]
    rng = np.percentile(lum[painted], 95) - np.percentile(lum[painted], 5)
    crunch = float(lap[m].mean() / max(rng, 8.0)) if m.sum() > 0 else 0.0
    return dict(blown=blown, neon=neon, crunch=crunch, crush=crush, glare=glare, lift=lift)


def judge(m):
    return [k for k, lim in LIMITS.items() if m[k] > lim]


def judge_pair(out, src):
    """the measures a bake pushed past PAIR_LIMITS over its source, with how far"""
    bad = {}
    for k, lim in PAIR_LIMITS.items():
        d = out[k] / max(src[k], 0.02) if k == 'crunch' else out[k] - src[k]
        if d > lim: bad[k] = d
    return bad


def report_pairs(pairs, quiet=False):
    """[(source png, baked png)] -> [(baked, {measure: rise})] for the deep-fried ones (printed); each baked file once"""
    bad = []; seen = set(); cache = {}
    def m(p):
        if p not in cache: cache[p] = metrics(p) if os.path.exists(p) else None
        return cache[p]
    for src, out in pairs:
        if out in seen or any(k in os.path.basename(out).lower() for k in SKIP): continue
        seen.add(out)
        a, b = m(out), m(src)
        if not a or not b: continue
        f = judge_pair(a, b)
        if f: bad.append((out, f))
    if not quiet:
        print(f'skin check: {len(seen)} baked skins against their sources, {len(bad)} look deep fried')
        for out, f in bad:
            print(f'  DEEP FRIED {out}: ' + ', '.join(f'{k} +{d:.2f} (limit {PAIR_LIMITS[k]})' if k != 'crunch' else f'crunch x{d:.2f} (limit {PAIR_LIMITS[k]})' for k, d in f.items()))
    if bad and os.environ.get('HCE_STRICT_SKINS') == '1':
        raise SystemExit(f'skin check failed: {len(bad)} deep-fried skins')
    return bad


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, fs in os.walk(p):
                out += [os.path.join(root, f) for f in fs if f.lower().endswith('.png')]
        elif p.lower().endswith('.png'): out.append(p)
    return [p for p in sorted(out) if not any(k in os.path.basename(p).lower() for k in SKIP)]


def report(paths, quiet=False, out_json=None):
    """score every texture under paths; print the deep-fried ones; returns [(path, failed measures, metrics)]"""
    bad = []; allm = {}
    for p in collect(paths):
        m = metrics(p)
        if m is None: continue
        allm[p] = m
        f = judge(m)
        if f: bad.append((p, f, m))
    if out_json: json.dump(allm, open(out_json, 'w'), indent=0)
    if not quiet:
        print(f'skin check: {len(allm)} textures, {len(bad)} look deep fried')
        for p, f, m in bad:
            print(f'  DEEP FRIED {p}: ' + ', '.join(f'{k} {m[k]:.2f} (limit {LIMITS[k]})' for k in f))
    if bad and os.environ.get('HCE_STRICT_SKINS') == '1':
        raise SystemExit(f'skin check failed: {len(bad)} deep-fried textures')
    return bad


if __name__ == '__main__':
    args = sys.argv[1:] or [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pack', 'models')]
    report(args)
