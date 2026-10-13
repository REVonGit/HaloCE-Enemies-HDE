// A Sentinel's hard-light shield bubble (drawn additively by its flare actor, so brightness is opacity): a faint
// see-through film, brighter toward its rim where you look through more of it, with a hex lattice shimmering across
// it and slow interference bands rolling over the surface
vec4 ProcessTexel()
{
	vec3 tint = getTexel(vTexCoord.st).rgb;
	vec3 n = normalize(vWorldNormal.xyz);
	vec3 v = normalize(pixelpos.xyz - uCameraPos.xyz);
	float fres = pow(1.0 - abs(dot(n, v)), 2.2);
	float t = timer;
	// the lattice, in the bubble's own texture space, its cells lighting up and dimming in turn
	vec2 h = vTexCoord.st * vec2(textureSize(tex, 0)) / 4.0;          // the texture's size sets the cell count (build_pack)
	h.x += mod(floor(h.y), 2.0) * 0.5;
	vec2 f = abs(fract(h) - 0.5);
	float edge = smoothstep(0.43, 0.5, max(f.x * 1.15 + f.y * 0.6, f.y * 1.2));
	float id = dot(floor(h), vec2(7.13, 3.71));
	float flick = 0.45 + 0.55 * sin(t * 2.6 + id * 1.9);
	// interference bands drifting through it (world space, so they roll over the sphere)
	vec3 p = pixelpos.xyz * 0.06;
	float bands = sin(p.x * 3.1 + t * 1.4) * sin(p.y * 2.7 - t * 1.1) * sin(p.z * 3.3 + t * 0.9);
	bands = smoothstep(0.2, 0.95, abs(bands));
	float film = 0.03 + 0.4 * fres;
	float shimmer = edge * (0.15 + 0.45 * flick) + bands * 0.1;
	vec3 col = tint * (film + shimmer) + vec3(1.0) * fres * 0.15;
	return vec4(min(col, vec3(1.0)), 1.0);
}
