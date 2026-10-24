// Halo's plasma energy shields, ported, on the shield flares (HCE_ShieldShell: a copy of the body a touch larger,
// drawn additively, its alpha the shield's glow: bright on a hit, fading). Two layers of Halo CE's 3D plasma noise
// (characters\elite\bitmaps\plasma shield noise, 32x32x32: pl_noise, its slices in an 8 x 4 sheet, extract_shader_maps.py)
// in the body's own space, each scaled and drifting its own way; where the two are equal the shield shows a line of
// lightning, with softer light either side. The glow (the flare's alpha) both dims it (the additive blend) and thins
// the lines, as Halo's intensity does.
//   default   Halo CE's characters\elite\shaders\shield plasma (shader_transparent_plasma): noise x6 drifting
//             (2, 0, -0.3) every 2.1 s and x4 drifting (0, 2, 0.5) every 3.2 s; tinted from its perpendicular colour
//             (looked at square on) to its parallel colour (at the rim).
//   HCE_H2    Halo 2's plasma_shield (the Sentinel Aggressor's bubble): noise x5 and x3, the same drifts; a centre line,
//             a sharp band and a wide band in their own colours over white, its glancing colour at the rim.
// The skin's texel is the wearer's shield colour (SHELL_TINT / SHIELD_TINT): every colour above is Halo's for the
// reference colour REF (the Elites' blue, the Aggressors' pale blue) and scaled channel by channel for any other.
const vec3 REF = vec3(0.45, 0.70, 1.00);
const float PUSH = 8.0;                                       // Halo's 0.065 world units, and a little more (the bulkier Halo 2 armour)

float plTex(ivec3 i)
{
	int z = i.z & 31;                                          // slice z: column z % 8, row z / 8 of the 8 x 4 sheet
	return texelFetch(pl_noise, ivec2((i.x & 31) + (z & 7) * 32, (i.y & 31) + (z >> 3) * 32), 0).r;
}

// the noise at p (1 = the volume's width), trilinear, wrapping
float plNoise(vec3 p)
{
	vec3 q = p * 32.0 - 0.5;
	ivec3 i = ivec3(floor(q));
	vec3 f = q - floor(q);
	float x00 = mix(plTex(i), plTex(i + ivec3(1, 0, 0)), f.x);
	float x10 = mix(plTex(i + ivec3(0, 1, 0)), plTex(i + ivec3(1, 1, 0)), f.x);
	float x01 = mix(plTex(i + ivec3(0, 0, 1)), plTex(i + ivec3(1, 0, 1)), f.x);
	float x11 = mix(plTex(i + ivec3(0, 1, 1)), plTex(i + ivec3(1, 1, 1)), f.x);
	return mix(mix(x00, x10, f.y), mix(x01, x11, f.y), f.z);
}

vec4 ProcessTexel()
{
	vec3 k = texelFetch(tex, ivec2(0, 0), 0).rgb / REF;       // the wearer's colour against Halo's own
	float glow = clamp(vColor.a, 0.0, 1.0);
	// the body's own space (Halo world units), so the plasma rides on it as it moves
	vec3 p = (inverse(ModelMatrix) * vec4(pixelpos.xyz, 1.0)).xyz;
	vec3 n = normalize(vWorldNormal.xyz);
	vec3 v = normalize(uCameraPos.xyz - pixelpos.xyz);
	float facing = abs(dot(n, v));                              // 1 square on, 0 at the rim
#ifdef HCE_H2
	float n0 = plNoise(p * 5.0 + vec3(2.0, 0.0, -0.3) * (timer / 2.1));
	float n1 = plNoise(p * 3.0 + vec3(0.0, 2.0, 0.5) * (timer / 3.2));
#else
	float n0 = plNoise(p * 6.0 + vec3(2.0, 0.0, -0.3) * (timer / 2.1));
	float n1 = plNoise(p * 4.0 + vec3(0.0, 2.0, 0.5) * (timer / 3.2));
#endif
	float d = abs(n0 - n1) / (0.35 + 0.65 * glow);              // a fading shield: thinner lines
	float centre = pow(clamp(1.0 - d * 30.0, 0.0, 1.0), 2.0);
	float sharp = pow(clamp(1.0 - d * 12.0, 0.0, 1.0), 2.0);
	float wide = pow(clamp(1.0 - d * 4.0, 0.0, 1.0), 2.0);
#ifdef HCE_H2
	vec3 col = centre * vec3(0.678, 0.957, 0.980)              // center_line
		+ sharp * vec3(0.467, 0.733, 1.0)                       // color_sharp
		+ wide * vec3(0.4, 0.671, 0.969) * 0.5                  // color_wide
		+ vec3(0.596, 0.0, 0.851) * pow(1.0 - facing, 2.0);     // glancing_color
#else
	vec3 tint = mix(vec3(0.651, 1.0, 1.0), vec3(0.627, 0.216, 1.0), 1.0 - facing);   // perpendicular .. parallel
	vec3 col = tint * (centre + sharp * 0.6 + wide * 0.25);
#endif
#ifndef HCE_H2
	// Halo pushes the flare out along the body's normals (its offset, 0.065 world units); a copy of the model can't be
	// grown that way here, so its depth is drawn PUSH map units nearer instead: the body no longer hides it
	gl_FragDepth = gl_FragCoord.z - (1.0 - gl_FragCoord.z) * PUSH / max(pixelpos.w, 1.0);
#endif
	return vec4(clamp(col * k, 0.0, 1.0), 1.0);
}
