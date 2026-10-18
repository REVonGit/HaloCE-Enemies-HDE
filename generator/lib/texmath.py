"""Texture maths shared by the extractors and build_pack.py: bump maps, normals rasterised into texture space, Halo's
cube maps, and the cube-map reflection Halo draws on armour, baked into a colour map.

Conventions:
  * images are float numpy arrays (H, W, C) with colours in 0..1 unless a function says otherwise
  * normals are unit vectors in the model's space (Halo's axes: x forward, y left, z up)
  * a cube map is six (H, W, 3) faces in Direct3D order: +x -x +y -y +z -z
"""
import numpy as np


def blur(a, r):
    """a gaussian blur of radius about r texels that wraps at the edges (textures tile)"""
    from scipy import ndimage
    return ndimage.gaussian_filter(a, r / 2.0, mode='wrap')


def height_from_normals(n):
    """the bump map's height field (Frankot-Chellappa: the surface whose slopes the normals give), zero mean"""
    gx = -n[..., 0] / np.maximum(n[..., 2], 0.2); gy = n[..., 1] / np.maximum(n[..., 2], 0.2)
    h, w = gx.shape
    u, v = np.meshgrid(np.fft.fftfreq(w) * 2 * np.pi, np.fft.fftfreq(h) * 2 * np.pi)
    d = u * u + v * v; d[0, 0] = 1
    z = (-1j * u * np.fft.fft2(gx) - 1j * v * np.fft.fft2(gy)) / d; z[0, 0] = 0
    return np.real(np.fft.ifft2(z))


def raster_normals(meshes, matfile, size, coverage=False):
    """(H, W, 3) normals per texel of the meshes using 'matfile' (gaps filled from the nearest covered texel).
    meshes: IQM meshes (iqm.read_iqm) with material, uv, nrm and tris; size: (W, H); coverage: also return the
    (H, W) mask of the texels the meshes actually cover"""
    from scipy import ndimage
    W_, H_ = size
    N = np.zeros((H_, W_, 3), np.float32); hit = np.zeros((H_, W_), bool)
    for m in meshes:
        if m['material'] != matfile or not len(m['tris']): continue
        uv = m['uv'] % 1.0 * np.array([W_ - 1, H_ - 1]); nr = m['nrm']
        for t in m['tris']:
            p = uv[t]; n = nr[t]
            x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
            if x1 - x0 > W_ * 0.6 or y1 - y0 > H_ * 0.6: continue        # wraps across the seam
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            v0, v1 = p[1] - p[0], p[2] - p[0]
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9: continue
            dx, dy = xs - p[0][0], ys - p[0][1]
            b1 = (dx * v1[1] - v1[0] * dy) / den; b2 = (v0[0] * dy - dx * v0[1]) / den; b0 = 1 - b1 - b2
            ins = (b0 >= -0.02) & (b1 >= -0.02) & (b2 >= -0.02)
            xi, yi = xs[ins] % W_, ys[ins] % H_
            N[yi, xi] = b0[ins, None] * n[0] + b1[ins, None] * n[1] + b2[ins, None] * n[2]
            hit[yi, xi] = True
    if hit.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~hit, return_indices=True)
        N = N[iy, ix]
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-6)
    return (N, hit) if coverage else N


def sample_cube(faces, r):
    """r (..., 3) directions -> colours (Direct3D cube face layout, Halo's axes)"""
    ax = np.abs(r); out = np.zeros(r.shape, np.float32)
    big = np.argmax(ax, -1); sgn = np.take_along_axis(r, big[..., None], -1)[..., 0] >= 0
    x, y, z = r[..., 0], r[..., 1], r[..., 2]
    for f, (axis, pos) in enumerate(((0, True), (0, False), (1, True), (1, False), (2, True), (2, False))):
        sel = (big == axis) & (sgn == pos)
        if not sel.any(): continue
        ma = ax[..., axis][sel]
        sc, tc = {0: (-z, -y) if pos else (z, -y), 1: (x, z) if pos else (x, -z), 2: (x, -y) if pos else (-x, -y)}[axis]
        u = (sc[sel] / ma + 1) / 2; v = (tc[sel] / ma + 1) / 2
        F = faces[f]; h, w = F.shape[:2]
        out[sel] = F[np.clip((v * (h - 1)).astype(int), 0, h - 1), np.clip((u * (w - 1)).astype(int), 0, w - 1)]
    return out


def bake_reflection(rgb, n, spec, faces, k=1.0):
    """a cube-map reflection baked into a colour map whose per-texel model-space normals are known: the paint's relief
    bends the normals, a view from the front reflects into the cube map, brighter toward grazing angles, added under
    the specular mask (rgb, n: (H, W, 3); spec: (H, W) 0..1; k: strength)"""
    from scipy import ndimage
    lum = ndimage.gaussian_filter(rgb.mean(axis=2), 1.2)
    gy, gx = np.gradient(lum)
    t1 = np.cross(n, np.array([0, 0, 1.0], np.float32)); t1 /= np.maximum(np.linalg.norm(t1, axis=2, keepdims=True), 1e-3)
    t2 = np.cross(n, t1)
    n = n + (gx[..., None] * t1 + gy[..., None] * t2) * 6.0
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    view = np.array([-1.0, 0.0, -0.25], np.float32); view /= np.linalg.norm(view)
    r = view - 2 * (n @ view)[..., None] * n
    env = np.clip(sample_cube(faces, r) * 1.15, 0, 1) ** 1.35 * 1.7
    fres = 0.75 + 0.5 * (1 - np.abs(n @ view)) ** 2
    sp = spec * k
    return np.clip(rgb * (1 - 0.3 * sp[..., None]) + env * (sp * fres)[..., None], 0, 1)
