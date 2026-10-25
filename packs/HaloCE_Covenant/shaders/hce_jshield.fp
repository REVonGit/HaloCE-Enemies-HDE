// Halo CE's Jackal shield (characters\jackal\shaders\jackal shield), ported: a shader_transparent_generic whose seven
// register-combiner stages are run here as the game ran them, over its own four maps (extract_shader_maps.py):
//   js_noise   the shield noise, twice: one copy sliding (-u 1.6 s, +v 1.1 s), the other (+u 1.4 s, -v 1.7 s)
//   js_offset  the rib pattern (alpha)
//   js_mask    the shield's shape (alpha: its body grey, its rim and the hand hole white) and the rim colour (rgb)
// The skin's own texel is the shield's colour (the rank's: Halo's change colour C). Drawn additively by the shield
// field actor (HCE_ShieldField), so black is see-through. Halo drives two things from the Jackal: 'shield hit flash'
// (its recent shield damage) stirs the noise into the ribs and pulls the colour toward red; it arrives here in the
// actor's alpha, just under 1: alpha = 1 - FLASH_BAND x flash (the output is divided by the alpha again, so the
// field keeps its brightness). HCE_ENF: the Sentinel Enforcer's shields (Halo 2's plasma_mask_offset, the same
// combiner over the Enforcer's hexagon noise, cracks and mask). JS_LAYERS (a define): the mesh's copies of each triangle.
const float FLASH_BAND = 0.1;

float slide(float period) { return fract(timer / period); }   // Halo's 'slide' function: 0 to 1 over the period

vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	vec3 tint = texelFetch(tex, ivec2(0, 0), 0).rgb;
	float a = max(vColor.a, 0.001);
	float F = clamp((1.0 - a) / FLASH_BAND, 0.0, 1.0);
	vec4 n0 = texture(js_noise, uv + vec2(-slide(1.6), slide(1.1)));
	vec4 n1 = texture(js_noise, uv + vec2(slide(1.4), -slide(1.7)));
	vec4 off = texture(js_offset, uv);
	vec4 m = texture(js_mask, uv);
	// stage 0: constant colour 0's alpha (0.25 at rest, 1 on a hit: 'A out' = the hit flash) blends the ribs into the
	// sliding noise; the second noise against grey in the alpha
	float c0a = 0.25 + 0.75 * F;
	float r = (1.0 - c0a) * off.a + c0a * n0.a;
	float ra = (1.0 - c0a) * 0.5 + c0a * n1.a;
	// stage 1: the rim and the hand hole (mask alpha) settle to grey
	r = clamp(m.a * 0.5 + (1.0 - m.a) * clamp(r, 0.0, 1.0), 0.0, 1.0);
	ra = clamp(m.a * 0.5 + (1.0 - m.a) * clamp(ra, 0.0, 1.0), 0.0, 1.0);
	// stage 2: their difference, about one half
	float d = clamp(r + 0.5 - ra, -1.0, 1.0);
	float da = clamp(ra + 0.5 - r, -1.0, 1.0);
	// stage 3: vertex colour 1 = the shield colour, toward constant colour 1 (red) by the flash; alpha: a peak where
	// the two layers meet (mux on scratch alpha >= 0.5, x4)
	vec3 v1 = mix(tint, vec3(1.0, 0.0, 0.0), F);
	float ca = clamp(da, 0.0, 1.0), cb = clamp(d, 0.0, 1.0);
	float s = clamp(4.0 * (ca >= 0.5 ? cb * cb : ca * ca), -1.0, 1.0);
	// stage 4: sharpened (mux: below one half nothing, above it (2x - 1) squared)
	ca = clamp(s, 0.0, 1.0);
	s = ca >= 0.5 ? (2.0 * ca - 1.0) * (2.0 * ca - 1.0) : 0.0;
	// stage 5: scratch colour 1 = 1 - mask alpha (the shield's body); the lines softened: s + s(1 - s)
	vec3 r1 = vec3(1.0 - m.a);
	ca = clamp(s, 0.0, 1.0);
	s = clamp(ca + ca * (1.0 - ca), 0.0, 1.0);
	// stage 6 (the output, added to the frame): the lines in the rim colour, the body in the shield's colour
	vec3 col = clamp(s * m.rgb + v1 * r1, 0.0, 1.0);
#ifdef JS_LAYERS
	col /= float(JS_LAYERS);           // a mesh that draws each triangle JS_LAYERS times (Halo 2's Jackal shield: 4): one layer's light
#endif
	return vec4(col / a, 1.0);               // (fullbright: the material's brightmap is all white)
}
