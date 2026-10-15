"""Worn metal for flat armour textures (the Brute kit's King Hit plates): their painted sheets are large even grey
fields, so on the model the plates read as smooth plastic. wear() bakes in, under a metal mask:

* relief: a height field from the sheet's own shading (its panel lines and rivets), lit from above, so the painted
  detail stands out as dents and raised edges;
* edge wear: the convex rims of that relief and of the mask's edges brightened to scuffed bare metal;
* grime: the hollows and the low-frequency blotches darkened toward an oily brown;
* scratches: fine streaks in a few directions, light on dark, the way a well-used plate catches the light;
* pitting: speckles of small dents.

Everything is seeded per texture name, so a rebuild gives the same bytes.

    from wornmetal import wear
    rgb = wear(rgb, metal_mask, seed='armour_common')   # rgb float HxWx3 in 0..1, mask HxW in 0..1
"""
import hashlib
import numpy as np
from scipy import ndimage


def _rng(seed):
    """a numpy Generator seeded from the md5 of str(seed), so the same name always gives the same noise"""
    return np.random.default_rng(int(hashlib.md5(str(seed).encode()).hexdigest()[:8], 16))


def _fbm(rng, h, w, octaves=5, base=8):
    """fractal value noise in 0..1, tiling"""
    out = np.zeros((h, w)); amp = 1.0; tot = 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.random((n, n))
        g = np.tile(g, (3, 3))                                    # wrap so the zoom tiles
        z = ndimage.zoom(g, (h * 3 / g.shape[0], w * 3 / g.shape[1]), order=3)[h:2 * h, w:2 * w]
        out += z[:h, :w] * amp; tot += amp; amp *= 0.55
    out /= tot
    return (out - out.min()) / max(1e-6, out.max() - out.min())


def _scratches(rng, h, w, count, length, width=1.0):
    """thin random streaks (0..1), mostly along a few shared directions"""
    img = np.zeros((h, w))
    dirs = rng.uniform(0, np.pi, 3)
    for _ in range(count):
        a = dirs[rng.integers(0, 3)] + rng.normal(0, 0.25)
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        L = rng.uniform(0.3, 1.0) * length
        t = np.linspace(0, 1, max(2, int(L * 4)))
        xs = (x0 + np.cos(a) * L * t).astype(int) % w
        ys = (y0 + np.sin(a) * L * t).astype(int) % h
        fade = np.sin(np.pi * t) * rng.uniform(0.4, 1.0)
        np.maximum.at(img, (ys, xs), fade)
    if width > 1: img = ndimage.grey_dilation(img, size=(int(width), int(width)))
    return ndimage.gaussian_filter(img, 0.5)


def wear(rgb, mask, seed='metal', strength=1.0):
    """rgb: HxWx3 float 0..1; mask: HxW 0..1 (1 metal). Returns the worn rgb"""
    h, w = mask.shape
    rng = _rng(seed)
    lum = rgb @ np.array([0.3, 0.59, 0.11])
    # relief: the sheet's own detail as height (small blur so panel lines read as grooves), lit from the top left
    hgt = ndimage.gaussian_filter(lum, 1.2) + 0.15 * ndimage.gaussian_filter(mask, 2.0)
    gy, gx = np.gradient(hgt)
    shade = np.clip(-(gx * 0.6 + gy * 0.8) * 12.0, -0.4, 0.4)
    # edges and hollows: the difference of two blurs (convex rims > 0, hollows < 0)
    cav = ndimage.gaussian_filter(hgt, 0.8) - ndimage.gaussian_filter(hgt, 2.5)
    rim = np.clip(cav * 16.0, 0, 1)
    hollow = np.clip(-cav * 12.0, 0, 1)
    # the mask's own boundary (where a plate ends) wears too
    medge = np.clip(ndimage.gaussian_gradient_magnitude(mask, 1.5) * 3.0, 0, 1)
    blot = _fbm(rng, h, w, 5, 4)                                  # large grime / wear patches
    fine = _fbm(rng, h, w, 4, 32)                                 # fine mottling
    chips = np.clip((_fbm(rng, h, w, 3, 48) - 0.45) * 4.0, 0, 1)      # broken, chipped wear, not a clean halo
    wearmask = np.clip((rim + medge * 0.5) * chips * (0.5 + 0.8 * fine) - 0.05, 0, 1)
    # scratches gather where the plate took the most knocks (the wear blotches)
    zone = np.clip((blot - 0.35) * 2.5, 0, 1)
    scr = _scratches(rng, h, w, int(h * w / 1400), min(h, w) * 0.08) * (0.35 + 0.65 * zone)
    scr_big = _scratches(rng, h, w, int(h * w / 16000), min(h, w) * 0.22) * zone
    pits = (rng.random((h, w)) > 0.9985).astype(float)
    pits = ndimage.gaussian_filter(pits, 0.7) * 3.0

    out = rgb.copy()
    grey = lum[..., None]
    bare = np.clip(grey * 0.55 + 0.45, 0, 1) * np.array([0.98, 0.98, 1.0])      # polished steel
    grime = np.array([0.20, 0.17, 0.13])
    # relief light/shadow
    out = out * (1 + shade[..., None] * 0.9)
    # mottled tone over the flat fields
    out = out * (0.86 + 0.28 * fine[..., None]) * (0.92 + 0.16 * blot[..., None])
    # grime in hollows and in the dirty blotches
    g = np.clip(hollow * 0.75 + np.clip(blot - 0.55, 0, 1) * 1.2, 0, 0.8)[..., None]
    out = out * (1 - g) + grime * g * (0.5 + grey)
    # scratches: light streaks, a dark lip beside the big ones
    out = out + (scr * 0.2 + scr_big * 0.28)[..., None] * (0.6 + 0.4 * fine[..., None])
    out = out - (ndimage.shift(scr_big, (1, 1), mode='wrap') * 0.07)[..., None]
    out = out - pits[..., None] * 0.10
    # streaks of grime running down from the hollows (rain and oil)
    drip = ndimage.gaussian_filter(np.clip(hollow - 0.2, 0, 1), (6.0, 0.8))
    drip = np.roll(drip, 4, axis=0) * (0.4 + 0.6 * fine)
    out = out * (1 - np.clip(drip * 0.5, 0, 0.35))[..., None]
    # scuffed bare metal on the rims
    wm = (wearmask * 0.85)[..., None]
    out = out * (1 - wm) + bare * wm
    k = (mask * strength)[..., None]
    return np.clip(rgb * (1 - k) + out * k, 0, 1)
