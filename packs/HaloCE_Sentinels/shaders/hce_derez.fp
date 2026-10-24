// Promethean derez (Halo 4's dissolve, recreated): a dying Knight comes apart in small square cells of hard light. Each
// cell burns out at its own moment, with a fine jagged fringe; the edge just ahead of the burn glows white-hot through
// gold to orange, and what has burnt through is gone. Halo 4's own shader is compiled into its maps, so this is the same look
// built in GLSL.
//
// It runs only while the actor's alpha is in the derez band (DEREZ_BAND below 1: the Knight's HCE_DissolveTick sets
// alpha = 1 - DEREZ_BAND * progress with STYLE_Translucent). At full alpha it is the plain skin. Below the band (the
// phase's half-translucency) it is plain translucency. The surviving texels are kept fully opaque
// (Base.a / vColor.a: the engine multiplies the output alpha by vColor.a).
const float DEREZ_BAND = 0.1;
const float CELLS = 40.0;          // cells across the skin (texture space)
const float EDGE = 0.10;           // the glowing fringe's width, in progress

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
	if(a >= 0.9999 || a < 1.0 - DEREZ_BAND) return;
	float p = clamp((1.0 - a) / DEREZ_BAND, 0.0, 1.0);
	// each cell's moment (mostly its own, a little of a coarser wave so whole patches go together), and a fine
	// jagged fringe inside it
	vec2 uv = vTexCoord.st;
	float cell = dzHash(floor(uv * CELLS));
	float wave = dzNoise(uv * 5.0 + vec2(timer * 0.05, 0.0));
	float n = clamp(cell * 0.65 + wave * 0.35 + (dzNoise(uv * CELLS * 4.0) - 0.5) * 0.08, 0.0, 1.0);
	float left = n - p * (1.0 + EDGE);                 // < 0: burnt through
	if(left <= 0.0) { material.Base = vec4(0.0); return; }
	float glow = 1.0 - smoothstep(0.0, EDGE, left);    // 1 at the burning edge
	vec3 hot = mix(vec3(1.0, 0.42, 0.06), mix(vec3(1.0, 0.78, 0.30), vec3(1.0, 0.97, 0.85), smoothstep(0.6, 1.0, glow)), smoothstep(0.2, 0.7, glow));
	// the whole surface warms as it goes, and the glow flickers
	float flick = 0.85 + 0.15 * sin(timer * 40.0 + cell * 50.0);
	material.Base.rgb = mix(base.rgb + vec3(0.25, 0.12, 0.02) * p, hot, glow * flick);
	material.Bright = max(material.Bright, vec4(vec3(glow), 1.0));
	material.Base.a = base.a / max(a, 0.001);           // x vColor.a in the engine: fully opaque
}
