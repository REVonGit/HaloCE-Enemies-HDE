"""Build the dialogue pk3 tree from Lewisk3/HaloDoomEnemies (Sounds/<Voice>/<Category> N.ogg).

Logical sounds: HCE/<Voice>/<Event>, played by HaloDoom_EnemyBase.HCE_Say().
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, re, sys, shutil
SRC = os.environ.get('HCE_VOICE_SRC', 'HaloDoomEnemies/Sounds')
OUT = os.environ.get('HCE_VOICE_OUT', 'voices')

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
}
# events a voice lacks borrow another of its own events
FALLBACK = {'KillPlayer': 'Taunt', 'Panic': 'Flee', 'Flee': 'Panic', 'PainMed': 'Pain', 'PainHeavy': 'PainMed',
            'Regroup': 'Alert', 'OnFire': 'PainHeavy', 'Kamikaze': 'Panic', 'Stuck': 'Panic', 'LeaderDead': 'Panic', 'Berserk': 'Taunt',
            'Taunt': 'Howl', 'Pain': 'PainMed', 'Death': 'DeathHard', 'DeathHard': 'Death'}

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    lines = ['// Halo CE enemy dialogue (sound files from Lewisk3/HaloDoomEnemies).',
             '// Logical names HCE/<Voice>/<Event> are played by HaloDoom_EnemyBase.HCE_Say().', '']
    total = 0
    for voice in sorted(os.listdir(SRC)):
        vdir = os.path.join(SRC, voice)
        vname = voice.replace(' ', '_')
        if not os.path.isdir(vdir): continue
        events = {}
        for fn in sorted(os.listdir(vdir)):
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
        for ev, fb in FALLBACK.items():
            if ev not in events and fb in events:
                lines.append(f'$alias HCE/{vname}/{ev} HCE/{vname}/{fb}')
        lines.append('')
    open(os.path.join(OUT, 'sndinfo.voices'), 'w').write('\n'.join(lines))
    print(total, 'files')

if __name__ == '__main__':
    main()
