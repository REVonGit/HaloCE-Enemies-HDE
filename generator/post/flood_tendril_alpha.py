import sys, glob, os, numpy as np
from PIL import Image
BG = np.array([49, 52, 49])
def mask_of(a):
    d = np.abs(a[..., :3].astype(int) - BG).sum(-1)
    return d > 14
done = 0
for root in sys.argv[1:]:
    for f in glob.glob(root + '/models/hce/*/skins/*.png'):
        im = Image.open(f)
        if im.size != (128, 128) or f.endswith('_plain.png'): continue
        a = np.asarray(im.convert('RGBA'))
        bgshare = (np.abs(a[..., :3].astype(int) - BG).sum(-1) <= 4).mean()
        if bgshare < 0.5: continue
        m = mask_of(a)
        # (a speck of noise in the card's grey: dropped; the claws' edges kept)
        out = a.copy(); out[..., 3] = np.where(m, 255, 0)
        Image.fromarray(out, 'RGBA').save(f); done += 1
        # the blood over that surface: cut to the same shape (blood<k>_<Char>_<n>.png beside the model)
        char = f.split('/models/hce/')[1].split('/')[0]; n = f.rsplit('_', 1)[1][:-4]
        for b in glob.glob(f'{root}/models/hce/{char}/blood?_{char}_{n}.png'):
            bi = Image.open(b).convert('RGBA'); ba = np.asarray(bi).copy()
            mm = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize(bi.size, Image.NEAREST)) > 127
            ba[..., 3] = np.where(mm, ba[..., 3], 0); Image.fromarray(ba, 'RGBA').save(b); done += 1
print('cut out', done)
