"""Build the dialogue pk3 tree from Lewisk3/HaloDoomEnemies (Sounds/<Voice>/<Category> N.ogg).

    HCE_VOICE_SRC=HaloDoomEnemies/Sounds python3 build_voices.py     # -> voices/ (HCE_VOICE_OUT)

Reads every <Voice>/ folder under SRC (plus voice_extra/, HCE_VOICE_EXTRA: lines extract_h2_grunt.py adds, or a
whole replacement set when the folder holds a REPLACE file), copies each .ogg to voices/sounds/hce_voice/<voice>/
<event>_NN.ogg and writes voices/sndinfo.voices: one HCE/<Voice>/<Event>/<n> entry per file, a $random
HCE/<Voice>/<Event> over them, and $alias lines for the events a voice lacks (FALLBACK). The packs ship that tree;
HaloDoom_EnemyBase.HCE_Say() plays HCE/<Voice>/<Event> for the voice named in the class's HCE_Voices.

To map a new source category to an event, add it to CAT; to give a voice a stand-in for an event it has no lines
for, add the event to FALLBACK. The copy is incremental (.sources.json), so louden_voices.py's levelling survives.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, re, sys, shutil
SRC = os.environ.get('HCE_VOICE_SRC', 'HaloDoomEnemies/Sounds')
OUT = os.environ.get('HCE_VOICE_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'voices'))
# extra lines added on top of the main source, same layout (<Voice>/<Category> N.ogg): extract_h2_grunt.py
EXTRA = os.environ.get('HCE_VOICE_EXTRA', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'voice_extra'))

# source category (lowercased, number stripped) -> pack events
# a file 'Pain 3.ogg' is category 'pain'; it is filed under every event listed (the first names the copied file).
# A category not here is skipped (printed). The event names are what HCE_Say() asks for; a new event needs a line in
# the ZScript that says it.
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
    # combat callouts: taking cover, flanked, searching, rallying, orders, warnings
    'cover': ['Cover'],
    'uncovered': ['Uncovered'],
    'search start': ['SearchStart'],
    'search clear': ['SearchClear'],
    'search fail': ['SearchFail'],
    'keep watch': ['KeepWatch'],
    'found foe': ['FoundFoe'],
    'join me': ['JoinMe'],
    'charge': ['Charge'],
    'investigate': ['Investigate'],
    'behind': ['Behind'],
    'sniper': ['Sniper'],
    'sword': ['Sword'],
    'up there': ['UpThere'],
    'down there': ['DownThere'],
    'fall back': ['FallBack'],
    'advance': ['Advance'],
}
# events a voice lacks borrow another of its own events
# event -> the event it is aliased to when a voice has no lines for it; chains are followed up to five steps
# (Thanks -> Acknowledge -> Regroup -> Alert), so a new event only needs its nearest neighbour here
FALLBACK = {'KillPlayer': 'Taunt', 'Panic': 'Flee', 'Flee': 'Panic', 'PainMed': 'Pain', 'PainHeavy': 'PainMed',
            'Regroup': 'Alert', 'OnFire': 'PainHeavy', 'Kamikaze': 'Panic', 'Stuck': 'Panic', 'LeaderDead': 'Panic', 'Berserk': 'Taunt',
            'Taunt': 'Howl', 'Pain': 'PainMed', 'Death': 'DeathHard', 'DeathHard': 'Death',
            # the squad's lines (Halo 2 has most; the CE-only voices borrow the nearest they have)
            'Scold': 'PainMed', 'AllyKilled': 'Scold', 'Betrayal': 'Taunt', 'Acknowledge': 'Regroup',
            'Thanks': 'Acknowledge', 'Wounded': 'PainHeavy', 'Forgive': 'Acknowledge', 'WorseWeapon': 'Scold',
            'TradeOk': 'Thanks', 'Refuse': 'WorseWeapon', 'ManDown': 'LeaderDead', 'HeardGunfire': 'Alert',
            'Cover': 'Regroup', 'Uncovered': 'Cover', 'SearchStart': 'HeardGunfire', 'SearchClear': 'SearchFail',
            'SearchFail': 'Regroup', 'KeepWatch': 'SearchFail', 'FoundFoe': 'Alert', 'JoinMe': 'Regroup', 'Charge': 'Berserk',
            'Investigate': 'SearchStart', 'Behind': 'Alert', 'Sniper': 'Alert', 'Sword': 'Alert', 'UpThere': 'Alert',
            'DownThere': 'Alert', 'FallBack': 'Flee', 'Advance': 'Regroup'}

def main():
    """copy every voice's lines from SRC (and EXTRA) into OUT and write OUT/sndinfo.voices; prunes copies whose
    source is gone. Takes nothing (the paths are module constants), prints the file count."""
    # incremental: a line whose source file is unchanged keeps its copy in OUT (louden_voices.py has levelled it in
    # place; copying it again would mean levelling every line again). .sources.json: OUT path -> source sha1
    import hashlib, json
    rec_path = os.path.join(OUT, '.sources.json')
    first = not os.path.exists(rec_path)                # an OUT from before the record: its copies are trusted
    rec = {} if first else json.load(open(rec_path))
    made = set(); new_rec = {}
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
            src_f = os.path.join(vdir, fn)
            h = hashlib.sha1(open(src_f, 'rb').read()).hexdigest()
            if not (os.path.exists(os.path.join(OUT, dst)) and (first or rec.get(dst) == h)):
                shutil.copy(src_f, os.path.join(OUT, dst))
            new_rec[dst] = h; made.add(dst)
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
    # lines no longer made go
    sd = os.path.join(OUT, 'sounds')
    for dp, _, fs in os.walk(sd):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), OUT)
            if rel not in made: os.remove(os.path.join(dp, f))
    json.dump(new_rec, open(rec_path, 'w'), indent=0, sort_keys=True)
    open(os.path.join(OUT, 'sndinfo.voices'), 'w').write('\n'.join(lines))
    print(total, 'files')

if __name__ == '__main__':
    main()
