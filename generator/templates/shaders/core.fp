// Sentinel Knight core: a ball of hard-light energy. The skin is its colour; on top, slow interfering plasma bands
// drifting through it, a pulse, a fresnel rim that runs hotter (whiter) at the edge, and the room reflected in its
// glassy shell from a cube map (six faces in a strip: +x -x +y -y +z -z, as the visor shader)
vec4 ProcessTexel()
{
	vec3 tint = getTexel(vTexCoord.st).rgb;
	vec3 n = normalize(vWorldNormal.xyz);
	vec3 v = normalize(pixelpos.xyz - uCameraPos.xyz);
	vec3 r = reflect(v, n);
	vec3 h = vec3(r.x, r.z, r.y);                      // GL (x, up, y) -> Halo (x, y, up)
	vec3 a = abs(h);
	float face; float sc; float tc; float ma;
	if(a.x >= a.y && a.x >= a.z) { ma = a.x; if(h.x > 0.0) { face = 0.0; sc = -h.z; tc = -h.y; } else { face = 1.0; sc = h.z; tc = -h.y; } }
	else if(a.y >= a.z) { ma = a.y; if(h.y > 0.0) { face = 2.0; sc = h.x; tc = h.z; } else { face = 3.0; sc = h.x; tc = -h.z; } }
	else { ma = a.z; if(h.z > 0.0) { face = 4.0; sc = h.x; tc = -h.y; } else { face = 5.0; sc = -h.x; tc = -h.y; } }
	vec2 fuv = clamp(vec2(sc, tc) / max(ma, 0.0001) * 0.5 + 0.5, 0.002, 0.998);
	vec3 env = texture(tex_cube, vec2((face + fuv.x) / 6.0, fuv.y)).rgb;
	float fres = pow(1.0 - abs(dot(n, v)), 2.0);
	// the energy: three slow waves through the ball (world units), their product a shifting web of brighter bands
	vec3 p = pixelpos.xyz * 0.35;
	float t = timer;
	float e = sin(p.x * 2.9 + t * 2.1) * sin(p.y * 2.5 - t * 1.7) * sin(p.z * 3.1 + t * 1.3);
	float bands = smoothstep(0.15, 0.9, abs(e));
	float pulse = 0.88 + 0.12 * sin(t * 3.2);
	vec3 col = tint * (0.55 + 0.75 * bands) * pulse;
	col += mix(tint, vec3(1.0), 0.45) * fres * 0.9;            // the hot rim
	col += env * mix(tint, vec3(1.0), 0.35) * (0.25 + 0.6 * fres); // the shell's reflection
	// the derez (derez.fp: alpha just under 1 is its colour slot and progress): the core flares, then breaks up and is gone by
	// halfway; otherwise kept opaque against the translucent style the derez runs in
	float al = vColor.a;
	if(al < 0.9999 && al >= 0.9)
	{
		float dp = fract(clamp((1.0 - al) / 0.1 * 8.0, 0.0, 7.9999));   // derez.fp's progress (its slot is the colour)
		float cell = fract(sin(dot(floor(vTexCoord.st * 24.0), vec2(127.1, 311.7))) * 43758.5453);
		if(cell < dp * 2.2 - 0.1) return vec4(0.0);
		col = mix(col, vec3(1.0, 0.9, 0.7), smoothstep(0.0, 0.5, dp) * 0.6);
		return vec4(min(col, vec3(1.0)), 1.0 / al);
	}
	// the shield flare's band (0.8 to 0.9: derez.fp) draws the body translucent: the core stays opaque
	return vec4(min(col, vec3(1.0)), al >= 0.8 && al < 0.9 ? 1.0 / al : 1.0);
}
