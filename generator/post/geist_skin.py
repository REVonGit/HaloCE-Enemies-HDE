# the Geist in the Covenant's colours, divided as the Covenant's craft are: the top purple, the underbelly grey. Which
# is which comes from the model itself: each texel takes the facing (the normal's height, bind pose) of the triangle
# it lies on, rasterised into the skin's UV space, so the line between them follows the hull's own shape.
# The lights (orange, cyan, green) and the blue of the gun are kept; the picture's shading and detail carry over.
import sys, numpy as np
sys.path.insert(0, '/home/claude/repos/HaloCE-Enemies-HDE/generator/lib')
from iqm import read_iqm
from PIL import Image, ImageDraw, ImageFilter
PUR = np.array([0.50, 0.30, 0.80]); GRY = np.array([0.56, 0.57, 0.62])
J, M, A = read_iqm('/tmp/claude-0/sk/Geist_bind.iqm')
for k in (0, 1):
    a = np.asarray(Image.open(f'/tmp/claude-0/sk/geist_geist_{k}_orig.png').convert('RGB')).astype(float) / 255
    H, W = a.shape[:2]
    up = Image.new('L', (W, H), 128); d = ImageDraw.Draw(up)
    for m in M:
        if not m['material'].endswith(f'_{k}.png'): continue
        for t in sorted(m['tris'], key=lambda t: m['nrm'][t, 2].mean()):     # (where pieces overlap, the upward face wins)
            nz = m['nrm'][t, 2].mean()
            d.polygon([(u * W, v * H) for u, v in m['uv'][t]], fill=int(np.clip(128 + nz * 127, 0, 255)))
    nz = np.asarray(up.filter(ImageFilter.GaussianBlur(2.5))) / 127.5 - 1
    top = np.clip((nz + 0.15) / 0.3, 0, 1)[..., None]                        # (a short soft line where it turns over)
    mx = a.max(-1); mn = a.min(-1); s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    lum = (a @ np.array([0.3, 0.59, 0.11]))[..., None]
    grey = ((s < 0.30) & (mx > 0.03)).astype(float)
    grey = np.asarray(Image.fromarray((grey * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)))[..., None] / 255.0
    col = PUR * top + GRY * (1 - top)
    col = np.clip(col * lum * 2.6, 0, 1)
    out = a * (1 - grey) + col * grey
    Image.fromarray((out * 255).astype(np.uint8)).save(f'geist_geist_{k}.png')
o = Image.new('RGB', (1024, 512))
for k in (0, 1): o.paste(Image.open(f'geist_geist_{k}.png').resize((512, 512)), (k * 512, 0))
o.save('/tmp/claude-0/sk/geist_new.png')
