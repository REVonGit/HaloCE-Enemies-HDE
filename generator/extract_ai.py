"""Dump actor variants (actv), actors (actr), units, collision, weapons for the pack's characters."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, re, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from tags import tag, HMap, LAYOUT, FMT, VEC
from extract_chars import CHARS, MAPS
from hce_paths import MAPS_DIR

SKIP = re.compile(r'^(unused|pad|reserved|runtime|garbage)')

def dump(m, st, addr, depth=0):
    L = LAYOUT.layout(st)
    out = {}
    for fn, (o, t, n) in L['fields'].items():
        if SKIP.match(fn): continue
        t = re.sub(r'^(struct|union)\s+', '', t.strip())
        a = addr + o
        def one(a):
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
    if not blk or not blk['count']: return []
    size = LAYOUT.layout(st)['size']
    return [dump(m, st, blk['addr'] + i * size) for i in range(blk['count'])]

def synthesize(variants):
    """Jackal ranks by shield colour: Minor (blue, plasma pistol), Major (orange, plasma rifle), Ultra (pink, needler).
    CE ships only Minor/Major plasma-pistol Jackals; Major is re-armed and Ultra is new, built on the Major biped."""
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
    # Hunter colours: White lobs plasma-caster grenades, Red sprays a flamethrower from the arm cannon
    H = 'characters\\hunter\\hunter'
    hun = variants.get(H)
    if hun:
        white = copy.deepcopy(hun)
        rc = white['ranged_combat']
        rc['reference'] = 'hce\\plasma caster'           # HDE weapon; not a Halo CE tag
        rc['maximum_firing_range'] = 18.0
        rc['combat_range_lower_bound'], rc['combat_range_upper_bound'] = 4.0, 12.0
        white['_hunter_color'] = 'white'; white['_late'] = True
        red = copy.deepcopy(hun)
        rc = red['ranged_combat']
        rc['reference'] = 'weapons\\flamethrower\\flamethrower'
        rc['maximum_firing_range'] = 7.0
        rc['combat_range_lower_bound'], rc['combat_range_upper_bound'] = 0.0, 3.0
        red['_hunter_color'] = 'red'; red['_late'] = True
        variants[H + ' white'] = white
        variants[H + ' red'] = red
    variants[J + 'jackal minor plasma pistol']['_rank'] = 'minor'
    del variants[J + 'jackal major plasma pistol']
    variants[J + 'jackal major plasma rifle'] = pr
    variants[J + 'jackal ultra needler'] = ultra
    return variants

if __name__ == '__main__':
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
