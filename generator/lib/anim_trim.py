"""Bodies keep only the animations something plays: smaller packs, faster loading, less memory.

An IQM stores every joint of every frame of every animation, and the bodies carry whole Halo animation graphs (the
Marines about 15,000 frames each) of which the classes play perhaps three quarters. The ZScript names every animation it
plays as a literal ('stand rifle idle', the HCE_AnimName tables, the loadouts', the scripted ones): none is built from
pieces at run time. So an animation whose name appears as no quoted string in any of the packs' ZScript (the main pack,
the add-on, the enemy API, the Standalone library) is never played, and trim() drops it from each body model
(models/<mdir>/<Char>/<Char>.iqm) in the given pack folders. A model none of whose animations is named (attachments,
debris: their one bind frame) is left alone.

Run on the built packs before they are split and zipped: build_digsite.py does it at its end, when both packs' code
is final (a quick build of the main pack alone keeps every animation)."""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def named(zs_dirs):
    """every quoted string in the .zsc / .zs files under zs_dirs"""
    out = set()
    for d in zs_dirs:
        for f in glob.glob(f'{d}/**/*.zs*', recursive=True):
            t = open(f, errors='replace').read()
            out |= set(re.findall(r"'([^'\n]{1,120})'", t)) | set(re.findall(r'"([^"\n]{1,120})"', t))
    return out


def trim(packs, zs_dirs):
    from iqm import read_iqm, write_iqm
    used = named(zs_dirs)
    n_files = n_anims = before = after = 0
    for pack in packs:
        for p in sorted(glob.glob(f'{pack}/models/*/*/*.iqm')):
            char = os.path.basename(os.path.dirname(p))
            if os.path.basename(p) != f'{char}.iqm': continue
            joints, meshes, anims = read_iqm(p)
            keep = [n for n in anims if n in used]
            if not keep or len(keep) == len(anims): continue
            before += os.path.getsize(p)
            alist = [dict(name=n, fps=30.0, loop=True, frames=anims[n]) for n in keep]
            write_iqm(p, [(n, pa, tuple(t), tuple(q), tuple(s)) for n, pa, t, q, s in joints], meshes, alist)
            after += os.path.getsize(p)
            n_files += 1; n_anims += len(anims) - len(keep)
    print(f'anim_trim: {n_anims} unplayed animations dropped from {n_files} bodies, {before / 1e6:.1f} -> {after / 1e6:.1f} MB')


if __name__ == '__main__':
    # anim_trim.py pack [pack ...] -- zsdir [zsdir ...]
    a = sys.argv[1:]
    i = a.index('--')
    trim(a[:i], a[i + 1:])
