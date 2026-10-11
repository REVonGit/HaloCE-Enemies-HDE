// Brute Captain hologram flag (Halo 2's plasma_mask_offset shader, approximated)
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	float t = timer;
	float wave = sin(uv.x * 7.0 - t * 3.1) * 0.018 * uv.x + sin(uv.y * 11.0 + t * 2.3) * 0.008;
	vec4 c = getTexel(uv + vec2(wave * 0.4, wave));
	float n = fract(sin(dot(floor(uv * vec2(32.0, 48.0)) + floor(t * 12.0), vec2(12.9898, 78.233))) * 43758.5453);
	float band = smoothstep(0.7, 1.0, sin(uv.y * 5.0 + uv.x * 2.0 - t * 1.7)) * 0.35;
	float scan = 0.78 + 0.22 * sin(uv.y * 90.0 - t * 14.0);
	float pulse = 0.85 + 0.15 * sin(t * 5.3);
	vec3 col = c.rgb * scan * pulse * (0.85 + 0.3 * n) + c.rgb * band;
	return vec4(min(col * 1.6, vec3(1.0)), c.a);
}
