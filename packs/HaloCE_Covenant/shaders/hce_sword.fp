// Halo energy sword blade: plasma flowing up the blade in streaks, a white-hot core along its length, the edges
// shimmering and the whole blade breathing; drawn fullbright
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	float t = timer;
	vec4 c = getTexel(uv);
	float w = sin(uv.y * 22.0 + t * 5.0) * 0.004 + sin(uv.y * 57.0 - t * 9.0) * 0.0025;
	vec4 c2 = getTexel(uv + vec2(w, 0.0));
	vec3 base = mix(c.rgb, c2.rgb, 0.6);
	float lum = max(base.r, max(base.g, base.b));
	vec3 hue = base / max(0.001, lum);
	float flow = 0.5 + 0.5 * sin(uv.y * 40.0 - t * 7.0 + sin(uv.x * 9.0 + t * 2.0) * 1.5);
	float streak = smoothstep(0.75, 1.0, flow);
	float core = smoothstep(0.55, 0.95, lum);
	float n = fract(sin(dot(floor(uv * vec2(48.0, 160.0)) + floor(t * 20.0), vec2(12.9898, 78.233))) * 43758.5453);
	float spark = step(0.97, n) * (1.0 - core);
	float breathe = 0.88 + 0.12 * sin(t * 3.3) + 0.05 * sin(t * 13.0);
	vec3 col = base * breathe * (0.85 + 0.35 * flow) + hue * streak * 0.35 + vec3(core * 0.55) + hue * spark * 0.6;
	return vec4(min(col, vec3(1.0)), c.a);
}
