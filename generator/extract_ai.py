"""Dump actor variants (actv), actors (actr), units, collision, weapons for the pack's characters.

    python3 extract_ai.py      # after extract_chars.py; -> $HCE_OUT/ai_data.json

Walks every Xbox campaign map in extract_chars.MAPS, takes each actor_variant whose biped is one of the pack's
(extract_chars.CHARS) and dumps it field by field, with the actor, biped, collision model and weapon tags it points
to, by the tag layouts in lib/tags.py (LAYOUT). build_pack.py reads ai_data.json for the enemies' health, shields,
weapons, firing ranges and colours. synthesize() adds the ranks Halo CE never shipped (the plasma-rifle Jackal Major,
the needler Jackal Ultra, the red and white Hunters) on top of the dumped ones.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, re, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from tags import tag, HMap, LAYOUT, FMT, VEC
from extract_chars import CHARS, MAPS
from hce_paths import MAPS_DIR

# layout fields left out of the dump (padding and the like)
SKIP = re.compile(r'^(unused|pad|reserved|runtime|garbage)')

def dump(m, st, addr, depth=0):
    """One struct of the map at addr, laid out by LAYOUT.layout(st), as a dict of field name -> value.

    Scalars and vectors are read as is, a tag_reference becomes the referenced tag's name (None if unresolved),
    a tag_block becomes dict(count, addr) for block_dump() to expand, nested structs recurse up to four levels and
    tag_data is dropped. Fixed arrays of up to 8 scalars become lists; larger ones are left out."""
    L = LAYOUT.layout(st)
    out = {}
    for fn, (o, t, n) in L['fields'].items():
        if SKIP.match(fn): continue
        t = re.sub(r'^(struct|union)\s+', '', t.strip())
        a = addr + o
        def one(a):
            """the value of one field of type t at address a (see dump)"""
            if t in FMT: return m.u(FMT[t], a)[0]
            if t in VEC: return list(m.u(VEC[t], a))
            if t == 'tag_reference':
                tid = m.u('I', a + 12)[0]
                tt = m.byid.get(tid)
                return tt['name'] if tt else None
            if t == 'tag_block':
                c, p = m.u('II', a)
                return dict(count=c, addr=p)
            if t == 'tag_data': return None
            if t in LAYOUT.structs and depth < 4:
                return dump(m, t, a, depth + 1)
            return None
        sz = LAYOUT.type_info(t)[0]
        if n == 1:
            out[fn] = one(a)
        elif t in FMT and n <= 8:
            out[fn] = [one(a + i * sz) for i in range(n)]
    return out

def flatten_obj(d):
    """collapse single-member wrapper structs (object/unit/biped)"""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and k in ('object', 'unit', 'biped', 'item', 'weapon', 'projectile'):
            out.update(v)
        else:
            out[k] = v
    return out

def block_dump(m, blk, st):
    """every element of a tag block (dump()'s dict(count, addr)) as dump()ed structs of layout st; [] when empty"""
    if not blk or not blk['count']: return []
    size = LAYOUT.layout(st)['size']
    return [dump(m, st, blk['addr'] + i * size) for i in range(blk['count'])]

def synthesize(variants):
    """Jackal ranks by shield colour: Minor (blue, plasma pistol), Major (orange, plasma rifle), Ultra (pink, needler).
    CE ships only Minor/Major plasma-pistol Jackals; Major is re-armed and Ultra is new, built on the Major biped.

    Takes and returns the variants dict (modified in place). A made-up variant copies a dumped one and overrides
    its ranged_combat reference, rate of fire and ranges, its vitality, and tags it with '_rank', '_hunter_color'
    and '_late' (a new class whose DoomEdNum goes after the existing ones). To change a synthesized rank's gun or
    health, edit the numbers here; to add another rank, deepcopy a base variant the same way and give it a new key."""
    import copy
    J = 'characters\\jackal\\'
    maj = variants.get(J + 'jackal major plasma pistol')
    epr = variants.get('characters\\elite\\elite minor\\elite minor plasma rifle')
    gne = variants.get('characters\\grunt\\grunt major needler')
    if not (maj and epr and gne): return variants
    pr = copy.deepcopy(maj)
    rc = pr['ranged_combat']
    rc['reference'] = epr['ranged_combat']['reference']
    for k in ('rate_of_fire', 'burst_geometry'): rc[k] = copy.deepcopy(epr['ranged_combat'][k])
    pr['_rank'] = 'major'
    ultra = copy.deepcopy(maj)
    rc = ultra['ranged_combat']
    rc['reference'] = gne['ranged_combat']['reference']
    for k in ('rate_of_fire', 'burst_geometry'): rc[k] = copy.deepcopy(gne['ranged_combat'][k])
    ultra['unit']['maximum_body_vitality'] = 100.0
    ultra['unit']['maximum_shield_vitality'] = 350.0
    ultra['_rank'] = 'ultra'; ultra['_late'] = True        # new class: DoomEdNum appended after the existing ones
    # Hunter ranks by colour: the Major is red and sprays a flamethrower from the arm cannon, the Ultra is white and lobs
    # plasma-caster grenades; both on the Major's body (Halo CE's own blue Major, the common Hunter's twin, is dropped)
    H = 'characters\\hunter\\hunter'
    hun, hmaj = variants.get(H), variants.get(H + ' major')
    if hun and hmaj:
        white = copy.deepcopy(hmaj)
        rc = white['ranged_combat']
        rc['reference'] = 'hce\\plasma caster'           # HDE weapon; not a Halo CE tag
        rc['maximum_firing_range'] = 18.0
        rc['combat_range_lower_bound'], rc['combat_range_upper_bound'] = 4.0, 12.0
        white['unit']['maximum_body_vitality'] = 450.0
        white['_hunter_color'] = 'white'; white['_rank'] = 'ultra'; white['_late'] = True
        red = copy.deepcopy(hmaj)
        rc = red['ranged_combat']
        rc['reference'] = 'weapons\\flamethrower\\flamethrower'
        rc['maximum_firing_range'] = 7.0
        rc['combat_range_lower_bound'], rc['combat_range_upper_bound'] = 0.0, 3.0
        red['_hunter_color'] = 'red'
        variants[H + ' major'] = red
        variants[H + ' ultra'] = white
    variants[J + 'jackal minor plasma pistol']['_rank'] = 'minor'
    del variants[J + 'jackal major plasma pistol']
    variants[J + 'jackal major plasma rifle'] = pr
    variants[J + 'jackal ultra needler'] = ultra
    return variants

if __name__ == '__main__':
    # every map in order: the first map that carries a variant, actor, biped, collision or weapon tag supplies it
    units = set(CHARS)
    variants = {}; actors = {}; bipeds = {}; colls = {}; weapons = {}; projs = {}
    for n in MAPS:
        m = HMap(f'{MAPS_DIR}/{n}.map')
        byname = {(t['cls'], t['name']): t for t in m.tags}
        for t in m.find('actv'):
            v = dump(m, 'actor_variant_definition', t['data'])
            if v.get('unit_reference') not in units or t['name'] in variants: continue
            v['change_colors_list'] = block_dump(m, v.get('change_colors'), 'actor_variant_change_colors')
            v['first_map'] = n
            variants[t['name']] = v
            a = v['actor_reference']
            if a and a not in actors:
                actors[a] = dump(m, 'actor_definition', byname[('actr', a)]['data'])
            u = v['unit_reference']
            if u and u not in bipeds:
                b = flatten_obj(dump(m, 'biped_definition', byname[('bipd', u)]['data']))
                b['change_colors_list'] = []
                cc = b.get('change_colors')
                if cc and cc['count']:
                    for c in block_dump(m, cc, 'object_change_color_definition'):
                        c['perms'] = block_dump(m, c['permutations'], 'object_change_color_permutation')
                        b['change_colors_list'].append(c)
                bipeds[u] = b
                cm = b.get('collision_model')
                if cm and cm not in colls:
                    colls[cm] = dump(m, 'collision_model', byname[('coll', cm)]['data'])
            w = v['ranged_combat']['reference'] if v.get('ranged_combat') else None
            if w and w not in weapons and ('weap', w) in byname:
                wd = flatten_obj(dump(m, 'weapon_definition', byname[('weap', w)]['data']))
                wd['triggers_list'] = []
                tb = wd.get('triggers')
                if tb and tb['count']:
                    for tr in block_dump(m, tb, 'weapon_trigger_definition') if 'weapon_trigger_definition' in LAYOUT.structs else []:
                        wd['triggers_list'].append(tr)
                weapons[w] = wd
    variants = synthesize(variants)
    json.dump(dict(variants=variants, actors=actors, bipeds=bipeds, collisions=colls, weapons=weapons),
              open(__import__('hce_paths').OUT + '/ai_data.json', 'w'), indent=1, default=str)
    print(len(variants), 'variants', len(actors), 'actors', len(bipeds), 'bipeds', len(colls), 'colls', len(weapons), 'weapons')
    for k in sorted(variants): print(' ', k)
