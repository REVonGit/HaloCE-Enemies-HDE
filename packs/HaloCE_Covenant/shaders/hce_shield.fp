// Halo energy shield (Jackal gauntlets): the field drifts and folds over itself, a hex lattice shows through
// with cells flickering on and off, bands of light sweep across it and the whole thing pulses
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	float t = timer;
	vec4 c = getTexel(uv + vec2(t * 0.06, sin(t * 0.7) * 0.03));
	vec4 c2 = getTexel(uv * 1.7 - vec2(t * 0.09, t * 0.04));
	vec3 base = (c.rgb + c2.rgb) * 0.5;
	vec2 h = uv * vec2(12.0, 20.0);
	h.x += mod(floor(h.y), 2.0) * 0.5;
	vec2 f = abs(fract(h) - 0.5);
	float edge = smoothstep(0.36, 0.5, max(f.x * 1.15 + f.y * 0.6, f.y * 1.2));
	float id = dot(floor(h), vec2(7.13, 3.71));
	float flick = 0.5 + 0.5 * sin(t * 3.0 + id * 1.7);
	float sweep = smoothstep(0.86, 1.0, sin(uv.y * 8.0 + uv.x * 3.0 - t * 2.6));
	float pulse = 0.82 + 0.18 * sin(t * 4.5);
	vec3 hue = base / max(0.001, max(base.r, max(base.g, base.b)));
	vec3 col = base * pulse + hue * (edge * (0.35 + 0.55 * flick) * 0.6 + sweep * 0.45);
	return vec4(min(col, vec3(1.0)), c.a);
}
