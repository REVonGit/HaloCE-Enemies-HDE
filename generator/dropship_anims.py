"""Halo CE's dropship passenger animations on the Covenant's models: the Elites', Grunts', Jackals' and Hunters' seat in
the Spirit's troop bay (Halo CE's c_dropship seat label, CD-passenger: its idle, standing in the bay behind the door, and
its two ways out, the hop down from the open bay to the ground), which the extraction leaves out with the rest of Halo
CE's vehicle seats. A map that flies the Covenant in (HDE-Maps' Firefight) seats them in its dropship's bays with
enemies_base.zsc's ride (HCE_RideSeat, HCE_RideOut: hce_core.zsc's HCE_RideService is the way in from another mod), and
those play these by name:
    cd-passenger idle      Halo CE's 'CD-passengerL01 pistol idle' (the Elite's first; the Hunter's 'CD-passengerL01 idle')
    cd-passenger exit%0    its first 'CD-passengerL01 exit'
    cd-passenger exit%1    its second
They are relative to the seat's marker, as Halo CE plays them: the idle stands on it, the exits end out in front of it and
below it (EXIT below: where each leaves the body, Halo world units ahead and up, for the ride to put the body down
there as it ends). The frames are Halo CE's own, on Halo CE's own skeleton, which is each model's: added to the pack's
models as they stand (read, the three animations put in, written back: nothing else in a model changes).

    HCE_HALO_SRC=<halo-ce-universal>/source python3 dropship_anims.py <b30.map (Xbox, as the other tools read it)>

Prints each exit's length (frames at 30 a second) and where it ends, which enemies_base.zsc's HCE_RideExit has by model."""
import os, sys, zlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'lib')]
MODELS = os.path.join(HERE, '..', 'packs', 'HaloCE_Covenant', 'models', 'hce')
# a race's graph, the models on its skeleton, its idle and its exits
RACES = [('elite', ['Elite/Elite.iqm', 'EliteSpecial/EliteSpecial.iqm'], 'CD-passengerL01 pistol idle%1', ['CD-passengerL01 exit%1', 'CD-passengerL01 exit%2']),
         ('grunt', ['Grunt/Grunt.iqm', 'GruntSpecOps/GruntSpecOps.iqm'], 'CD-passengerL01 pistol idle', ['CD-passengerL01 exit%1', 'CD-passengerL01 exit%2']),
         ('jackal', ['Jackal/Jackal.iqm', 'JackalMajor/JackalMajor.iqm'], 'CD-passengerL01 pistol idle', ['CD-passengerL01 exit%0', 'CD-passengerL01 exit%1']),
         ('hunter', ['Hunter/Hunter.iqm'], 'CD-passengerL01 idle', ['CD-passengerL01 exit%1', 'CD-passengerL01 exit%2'])]


def open_map(path):
    """an Xbox map as the readers take it: whole (the file is the header and the rest deflated)"""
    from halomap import HMap
    d = open(path, 'rb').read()
    if d[0x800:0x802] == b'\x78\x9c':
        tmp = os.path.join('/dev/shm' if os.path.isdir('/dev/shm') else os.path.dirname(path), os.path.basename(path) + '.whole')
        if not os.path.exists(tmp): open(tmp, 'wb').write(d[:0x800] + zlib.decompress(d[0x800:]))
        path = tmp
    return HMap(path)


def main(mapfile):
    import be_anims
    from iqm import read_iqm, write_iqm
    m = open_map(mapfile)
    for race, files, idle, exits in RACES:
        A, nodes = be_anims.graph(m, f'characters\\{race}\\{race}')
        new = {'cd-passenger idle': A[idle]}
        for k, e in enumerate(exits): new['cd-passenger exit%%%d' % k] = A[e]
        for n, a in new.items():
            end = np.array(a.frames[-1][0][0]) - np.array(new['cd-passenger idle'].frames[0][0][0])
            print(race, n, a.nframes, 'frames; the pelvis ends', np.round(end, 3), 'from the idle\'s')
        for f in files:
            p = os.path.join(MODELS, f); J, M, AN = read_iqm(p)
            assert [j[0] for j in J] == nodes, (f, 'not the graph\'s skeleton')
            # (after the model's own, in their order: every frame it had keeps its number)
            for n in new: AN.pop(n, None)
            for n, a in new.items(): AN[n] = [[(t, q, sc) for (t, q, sc) in fr] for fr in a.frames]
            write_iqm(p, J, M, [dict(name=n, fps=30.0, loop=True, frames=AN[n]) for n in AN])
            print('  ', f, len(AN), 'animations')


if __name__ == '__main__': main(sys.argv[1])
