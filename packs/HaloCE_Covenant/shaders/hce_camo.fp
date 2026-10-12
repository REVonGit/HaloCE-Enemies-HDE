// Halo active camo: the body all but vanishes, a faint refracting outline; slow bands of light ripple over it now and
// then, with a fine sparkle
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	vec4 c = getTexel(uv);
	float t = timer;
	float w = sin(uv.y * 34.0 - t * 4.0 + sin(uv.x * 11.0 + t * 1.3) * 2.2);
	float band = smoothstep(0.86, 1.0, w);
	float n = fract(sin(dot(floor(uv * 64.0) + floor(t * 14.0), vec2(12.9898, 78.233))) * 43758.5453);
	vec3 body = c.rgb * 0.25 + vec3(0.30, 0.36, 0.42);
	vec3 col = mix(body, vec3(0.80, 0.92, 1.0), band);
	float a = 0.12 + band * 0.40 + step(0.95, n) * 0.15;
	return vec4(col, c.a * a);
}
