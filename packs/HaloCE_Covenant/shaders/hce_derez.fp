// Every enemy skin's shader: the energy-shield flare while alive, and the Promethean derez when Forerunner hard light kills.
//
// Promethean derez (Halo 4's dissolve, recreated): a body killed by Forerunner hard light comes apart in small square
// cells. Each cell burns out at its own moment, with a fine jagged fringe; the edge just ahead of the burn glows
// white-hot through the colour of whatever killed it, and what has burnt through is gone. Halo 4's own shader is
// compiled into its maps, so this is the same look built in GLSL. On every enemy skin.
//
// It runs only while the actor's alpha is in the derez band (just under 1): alpha = 1 - DEREZ_BAND x (slot + progress)
// / SLOTS, set by HaloDoom_EnemyBase.HCE_DerezTick (or a Knight's HCE_DissolveTick) with STYLE_Translucent. slot picks
// the colour from PALETTE (the same order as HCE_DerezColor). At full alpha it is the plain skin; below the band (a
// Knight's phase, active camo) plain translucency. The surviving texels are kept fully opaque (Base.a / vColor.a: the
// engine multiplies the output alpha by vColor.a).
//
// The shield flare (Halo's energy shield lighting up when it's hit or recharging; it used to be a second, glowing copy
// of the model): alpha in the band below, 0.9 - DEREZ_BAND x (tint + strength) / SLOTS, set by
// HaloDoom_EnemyBase.HCE_ShieldGlowTick; tint from shieldColour (build_pack.SHIELD_PALETTE). Soft cells of light with
// bright sparks drift over the body in the shield's colour, brightest at its silhouette's rim.
const float DEREZ_BAND = 0.1;
const float SLOTS = 8.0;
const float CELLS = 40.0;          // cells across the skin (texture space)
const float EDGE = 0.10;           // the glowing fringe's width, in progress

// 0 the Knights' own (Halo 4's derez orange), 1 Light Rifle, 2 Binary Rifle, 3 Scattershot (orange; its cells take the
// purple too: SCATTER_PURPLE), 4 purple (unused), 5 Boltshot, 6 Sentinel Beam, 7 Unmaker
vec3 dzColour(int slot)
{
	if(slot == 1) return vec3(0.0, 0.38, 1.0);
	if(slot == 2) return vec3(0.0, 1.0, 0.58);
	if(slot == 3) return vec3(0.98, 0.69, 0.0);
	if(slot == 4) return vec3(0.57, 0.0, 0.98);
	if(slot == 5) return vec3(0.02, 0.17, 0.94);
	if(slot == 6) return vec3(1.0, 0.97, 0.19);
	if(slot == 7) return vec3(1.0, 0.65, 0.0);
	return vec3(1.0, 0.42, 0.06);
}

const vec3 SCATTER_PURPLE = vec3(0.57, 0.0, 0.98);

// the shield flare's colours (build_pack.SHIELD_PALETTE, written in by derez_shader)
vec3 shieldColour(int slot)
{
	if(slot == 0) return vec3(0.450, 0.700, 1.000);
	if(slot == 1) return vec3(1.000, 0.780, 0.300);
	if(slot == 2) return vec3(0.550, 0.850, 1.000);
	if(slot == 3) return vec3(1.000, 0.620, 0.220);
	return vec3(0.45, 0.70, 1.0);
}

float dzHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float dzNoise(vec2 p)
{
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	return mix(mix(dzHash(i), dzHash(i + vec2(1.0, 0.0)), f.x), mix(dzHash(i + vec2(0.0, 1.0)), dzHash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void SetupMaterial(inout Material material)
{
	vec4 base = getTexel(vTexCoord.st);
	material.Base = base;
	material.Normal = ApplyNormalMap(vTexCoord.st);
	material.Bright = texture(brighttexture, vTexCoord.st);
	float a = vColor.a;
	if(a < 0.9 && a >= 0.9 - DEREZ_BAND)
	{
		// the shield flare
		float sx = clamp((0.9 - a) / DEREZ_BAND * SLOTS, 0.0, SLOTS - 0.0001);
		float str = fract(sx);
		vec3 sc = shieldColour(int(floor(sx)));
		vec3 nrm = normalize(vWorldNormal.xyz);
		vec3 view = normalize(pixelpos.xyz - uCameraPos.xyz);
		float rim = pow(1.0 - abs(dot(nrm, view)), 2.0);
		vec2 q = pixelpos.xz * 0.09 + vec2(0.0, pixelpos.y * 0.09) + vec2(timer * 0.35, -timer * 0.5);
		float v = dzNoise(q * 1.7) * 0.85 + step(0.985, dzHash(floor(q * 9.0 + timer * 3.0))) * 0.9;
		v = pow(clamp(v, 0.0, 1.0), 1.4);
		vec3 sh = sc * (0.25 + 0.85 * v) + pow(v, 4.0) * 0.5;
		float k = str * (0.55 + 0.9 * rim);
		material.Base.rgb = min(base.rgb + sh * k, vec3(1.0));
		material.Bright = max(material.Bright, vec4(vec3(min(1.0, k)), 1.0));
		material.Base.a = base.a / max(a, 0.001);
		return;
	}
	if(a >= 0.9999 || a < 1.0 - DEREZ_BAND) return;
	float x = clamp((1.0 - a) / DEREZ_BAND * SLOTS, 0.0, SLOTS - 0.0001);
	int slot = int(floor(x));
	float p = fract(x);
	vec3 c = dzColour(slot);
	if(slot == 3 && dzHash(floor(vTexCoord.st * CELLS) + 7.3) > 0.5) c = SCATTER_PURPLE;   // the Scattershot: both its colours
	// each cell's moment (mostly its own, a little of a coarser wave so whole patches go together), and a fine
	// jagged fringe inside it
	vec2 uv = vTexCoord.st;
	float cell = dzHash(floor(uv * CELLS));
	float wave = dzNoise(uv * 5.0 + vec2(timer * 0.05, 0.0));
	float n = clamp(cell * 0.65 + wave * 0.35 + (dzNoise(uv * CELLS * 4.0) - 0.5) * 0.08, 0.0, 1.0);
	float left = n - p * (1.0 + EDGE);                 // < 0: burnt through
	if(left <= 0.0) { material.Base = vec4(0.0); return; }
	float glow = 1.0 - smoothstep(0.0, EDGE, left);    // 1 at the burning edge
	// deep colour at the fringe's outside, the colour itself, then white-hot at the edge
	vec3 hot = mix(c * 0.75, mix(mix(c, vec3(1.0), 0.3), mix(c, vec3(1.0), 0.88), smoothstep(0.6, 1.0, glow)), smoothstep(0.2, 0.7, glow));
	if(slot == 0) hot = mix(vec3(1.0, 0.42, 0.06), mix(vec3(1.0, 0.78, 0.30), vec3(1.0, 0.97, 0.85), smoothstep(0.6, 1.0, glow)), smoothstep(0.2, 0.7, glow));
	// the whole surface takes on the colour as it goes, and the glow flickers
	float flick = 0.85 + 0.15 * sin(timer * 40.0 + cell * 50.0);
	material.Base.rgb = mix(base.rgb + c * 0.25 * p, hot, glow * flick);
	material.Bright = max(material.Bright, vec4(vec3(glow), 1.0));
	material.Base.a = base.a / max(a, 0.001);          // x vColor.a in the engine: fully opaque
}
