# the Flood Grunt's armour in Halo's Grunt rank colours: tinted copies of its armour skins (0, 1; 3 is 0's picture)
import sys, numpy as np, colorsys
from PIL import Image
D = sys.argv[1] + '/models/hce/FloodGrunt/skins/'
RANKS = {'minor': (1.0, 0.45, 0.08), 'major': (0.72, 0.13, 0.09), 'specops': (0.16, 0.16, 0.19)}
def armour_mask(a):
    rgb = a[..., :3] / 255.0
    mx = rgb.max(-1); mn = rgb.min(-1); s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    greenish = (g >= r * 0.97) & (b < g * 0.92)           # the Flood flesh: olive green
    bluish = b > r * 1.08                                # the methane tank, the mask's glass
    m = np.clip((0.34 - s) / 0.12, 0, 1) * np.clip((mx - 0.22) / 0.12, 0, 1)
    m = np.where(greenish | bluish, 0, m)
    from PIL import ImageFilter
    mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    return np.asarray(mi) / 255.0   # (specks in the flesh dropped, the plates' edges soft)
for k in (0, 1):
    src = Image.open(D + f'floodgrunt_floodgrunt_{k}.png').convert('RGBA'); a = np.asarray(src).astype(float)
    m = armour_mask(a)[..., None]
    lum = (a[..., :3] / 255.0) @ np.array([0.3, 0.59, 0.11])
    for name, c in RANKS.items():
        c = np.array(c)
        tint = np.clip(lum[..., None] * c * 1.55, 0, 1) * 255
        if name == 'specops': tint = np.clip(lum[..., None] * 0.55 * 255 + 8, 0, 255) * np.array([0.95, 0.95, 1.05])
        out = a.copy(); out[..., :3] = a[..., :3] * (1 - m) + tint * m
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA').save(D + f'floodgrunt_{name}_{k}.png')
print('ok')
