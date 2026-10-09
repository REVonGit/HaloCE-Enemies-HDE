"""Build the dialogue pk3 tree from Lewisk3/HaloDoomEnemies (Sounds/<Voice>/<Category> N.ogg).

Logical sounds: HCE/<Voice>/<Event>, played by HaloDoom_EnemyBase.HCE_Say().
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, re, sys, shutil
SRC = os.environ.get('HCE_VOICE_SRC', 'HaloDoomEnemies/Sounds')
OUT = os.environ.get('HCE_VOICE_OUT', 'voices')
# extra lines added on top of the main source, same layout (<Voice>/<Category> N.ogg): extract_h2_grunt.py
EXTRA = os.environ.get('HCE_VOICE_EXTRA', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'voice_extra'))

# source category (lowercased, number stripped) -> pack events
CAT = {
    'alert': ['Alert'], 'taunt': ['Taunt'], 'death': ['Death'], 'death nrml': ['Death'],
    'kill player': ['KillPlayer'], 'pain': ['Pain', 'PainMed'], 'pain nrml': ['Pain'], 'pain med': ['PainMed'],
    'pain xtr': ['PainHeavy'], 'agonized': ['PainHeavy'], 'panic': ['Panic'], 'cower': ['Panic'], 'flee': ['Flee'],
    'regroup': ['Regroup'], 'leader dead': ['LeaderDead'], 'grenade thrw': ['GrenadeThrow'],
    'enemy grenade': ['EnemyGrenade'], 'on fire': ['OnFire'], 'stuck': ['Stuck'], 'kamakaze': ['Kamikaze'],
    'kamikaze': ['Kamikaze'], 'berserk': ['Berserk'], 'melee': ['Melee'], 'melting': ['Melting'],
    # creatures (Drinol, Blind Wolf)
    'death xtr': ['DeathHard'], 'grave injury': ['PainHeavy', 'PainMed'], 'sonic roar': ['Roar', 'Berserk'],
    'howl': ['Howl', 'Alert', 'Berserk'], 'idle': ['Idle'], 'bite': ['Melee'],
    # Marines and the player's squad
    'scold': ['Scold'], 'betrayal': ['Betrayal'], 'ally killed': ['AllyKilled'], 'acknowledge': ['Acknowledge'],
    'thanks': ['Thanks'], 'wounded': ['Wounded'], 'forgive': ['Forgive'], 'worse weapon': ['WorseWeapon'],
    'trade ok': ['TradeOk'], 'refuse': ['Refuse'],
    # a comrade killed in sight; gunfire heard before the enemy is seen
    'man down': ['ManDown'], 'heard gunfire': ['HeardGunfire'],
}
# events a voice lacks borrow another of its own events
FALLBACK = {'KillPlayer': 'Taunt', 'Panic': 'Flee', 'Flee': 'Panic', 'PainMed': 'Pain', 'PainHeavy': 'PainMed',
            'Regroup': 'Alert', 'OnFire': 'PainHeavy', 'Kamikaze': 'Panic', 'Stuck': 'Panic', 'LeaderDead': 'Panic', 'Berserk': 'Taunt',
            'Taunt': 'Howl', 'Pain': 'PainMed', 'Death': 'DeathHard', 'DeathHard': 'Death',
            # the squad's lines (Halo 2 has most; the CE-only voices borrow the nearest they have)
            'Scold': 'PainMed', 'AllyKilled': 'Scold', 'Betrayal': 'Taunt', 'Acknowledge': 'Regroup',
            'Thanks': 'Acknowledge', 'Wounded': 'PainHeavy', 'Forgive': 'Acknowledge', 'WorseWeapon': 'Scold',
            'TradeOk': 'Thanks', 'Refuse': 'WorseWeapon', 'ManDown': 'LeaderDead', 'HeardGunfire': 'Alert'}

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    lines = ['// Halo CE enemy dialogue (sound files from Lewisk3/HaloDoomEnemies).',
             '// Logical names HCE/<Voice>/<Event> are played by HaloDoom_EnemyBase.HCE_Say().', '']
    total = 0
    extra = set(os.listdir(EXTRA)) if os.path.isdir(EXTRA) else set()
    for voice in sorted(set(os.listdir(SRC)) | extra):
        vname = voice.replace(' ', '_')
        dirs = [d for d in (os.path.join(SRC, voice), os.path.join(EXTRA, voice)) if os.path.isdir(d)]
        if os.path.exists(os.path.join(EXTRA, voice, 'REPLACE')):            # this extra set replaces the main one
            dirs = [os.path.join(EXTRA, voice)]
        if not dirs: continue
        events = {}
        for vdir, fn in [(d, f) for d in dirs for f in sorted(os.listdir(d))]:
            if not fn.lower().endswith('.ogg'): continue
            cat = re.sub(r'\s*\d+$', '', fn[:-4]).strip().lower()
            if cat not in CAT: print('skip', voice, fn); continue
            ev0 = CAT[cat][0]
            n = sum(len(v) for v in events.values())
            dst = f'sounds/hce_voice/{vname.lower()}/{ev0.lower()}_{n:02d}.ogg'
            os.makedirs(os.path.join(OUT, os.path.dirname(dst)), exist_ok=True)
            shutil.copy(os.path.join(vdir, fn), os.path.join(OUT, dst))
            total += 1
            for ev in CAT[cat]:
                events.setdefault(ev, []).append(dst)
        lines.append(f'// ---- {voice}')
        for ev in sorted(events):
            ids = []
            for i, path in enumerate(events[ev]):
                sid = f'HCE/{vname}/{ev}/{i}'
                lines.append(f'{sid} "{path}"'); ids.append(sid)
            lines.append(f'$random HCE/{vname}/{ev} {{ {" ".join(ids)} }}')
        for ev in FALLBACK:
            if ev in events: continue
            fb, k = FALLBACK.get(ev), 0
            while fb and fb not in events and k < 5: fb, k = FALLBACK.get(fb), k + 1   # a chain: Thanks -> Acknowledge -> Regroup
            if fb in events: lines.append(f'$alias HCE/{vname}/{ev} HCE/{vname}/{fb}')
        lines.append('')
    open(os.path.join(OUT, 'sndinfo.voices'), 'w').write('\n'.join(lines))
    print(total, 'files')

if __name__ == '__main__':
    main()
