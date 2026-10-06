"""Close the Halo CE Marines' mouths. Every CE Marine face texture is painted with the mouth wide open (the
infamous gape); this finds the dark mouth opening under the nose and paints it shut: the hole is inpainted
from the lips and skin around it, then a soft closed-lip line is drawn across where the mouth was.

    python3 marine_faces.py        # out/models/Marine*/: the face textures (originals kept as <name>_open.png)
Run after extract_chars.py (it rewrites the textures) and before blood_kit.py / build_pack.py."""
import os, sys, json, shutil
import numpy as np
import cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
OUT = os.environ.get('HCE_OUT', os.path.join(HERE, 'out'))

def face_textures(char):
    meta = json.load(open(f'{OUT}/models/{char}/{char}.json'))
    names = meta.get('mesh_names') or []
    from collections import Counter
    heads = [(n, mat) for n, mat in zip(names, meta['meshes']) if n.startswith('head.') and 'shared' not in n and n != 'head.__base']
    used = Counter(mat for _, mat in heads)
    # a face texture belongs to one head; a texture several heads share is their hat / helmet atlas
    return sorted(mat for mat, k in used.items() if k == 1)

def find_mouth(img):
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0]
    x0, x1, y0, y1 = int(0.52 * w), int(0.90 * w), int(0.58 * h), int(0.84 * h)
    box = L[y0:y1, x0:x1]
    skin = np.median(box)
    dark = (box < skin * 0.55).astype(np.uint8)
    n, lab_, st, cen = cv2.connectedComponentsWithStats(dark, 8)
    best = None
    for i in range(1, n):
        x, y, ww, hh, area = st[i]
        if area < 8 or ww < hh * 1.2 or ww > 0.35 * w: continue           # a mouth is wider than tall
        score = area * (1 - abs((x + ww / 2) - (box.shape[1] * 0.5)) / box.shape[1])
        if best is None or score > best[0]: best = (score, i, x, y, ww, hh)
    if best is None: return None
    _, i, x, y, ww, hh = best
    mask = np.zeros(L.shape, np.uint8)
    mask[y0:y1, x0:x1][lab_ == i] = 255
    return mask, (x0 + x, y0 + y, ww, hh)

def close_mouth(path):
    img = cv2.imread(path)
    r = find_mouth(img)
    if r is None: return False
    mask, (x, y, ww, hh) = r
    # the whole opening (teeth and tongue too, not just the dark): an ellipse over it, a little larger
    ell = np.zeros(mask.shape, np.uint8)
    cv2.ellipse(ell, (int(x + ww / 2), int(y + hh / 2)), (int(ww * 0.62) + 1, int(hh * 0.85) + 1), 0, 0, 360, 255, -1)
    grow = cv2.dilate(mask | ell, np.ones((3, 3), np.uint8), iterations=1)
    # lip colour: the ring just outside the opening
    ring = cv2.dilate(grow, np.ones((3, 3), np.uint8), iterations=2) & ~grow
    lipc = np.median(img[ring > 0].astype(np.float32), 0)
    fixed = cv2.inpaint(img, grow, 4, cv2.INPAINT_TELEA)
    # the lips meeting: a soft dark line, slightly curved, across the old opening
    line = np.zeros(mask.shape, np.float32)
    cy = y + hh * 0.5
    pts = np.array([[x - 1, cy], [x + ww * 0.5, cy + hh * 0.12], [x + ww + 1, cy]], np.float32)
    curve = np.array([(1 - t) ** 2 * pts[0] + 2 * (1 - t) * t * pts[1] + t ** 2 * pts[2] for t in np.linspace(0, 1, 40)], np.int32)
    cv2.polylines(line, [curve], False, 1.0, 1, cv2.LINE_AA)
    line = cv2.GaussianBlur(line, (3, 3), 0.7)
    # lips: a soft band of the lip colour around the closed line, the line itself a gentle shadow, fading at the corners
    band = np.zeros(mask.shape, np.float32)
    cv2.ellipse(band, (int(x + ww / 2), int(cy)), (int(ww * 0.5), max(1, int(hh * 0.35))), 0, 0, 360, 1.0, -1)
    band = cv2.GaussianBlur(band, (5, 5), 1.2) * 0.45
    out = fixed.astype(np.float32) * (1 - band[..., None]) + lipc * 0.92 * band[..., None]
    lip = out * (1 - 0.38 * line[..., None])
    cv2.imwrite(path, np.clip(lip, 0, 255).astype(np.uint8))
    return (x, y, ww, hh)

def main():
    for char in ('Marine', 'MarineArmored'):
        for mat in face_textures(char):
            p = f'{OUT}/models/{char}/{mat}'
            keep = p[:-4] + '_open.png'
            if not os.path.exists(keep): shutil.copy(p, keep)
            else: shutil.copy(keep, p)                     # always start from the original
            r = close_mouth(p)
            print(char, mat, 'closed' if r else 'no mouth found', r or '')

if __name__ == '__main__':
    main()
