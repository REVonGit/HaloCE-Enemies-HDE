// Halo CE visor: a reflection cube map (six faces in a strip: +x -x +y -y +z -z), tinted, with fresnel
vec4 ProcessTexel()
{
	vec4 tint = getTexel(vTexCoord.st);
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
	vec3 col = tint.rgb * 0.25 + env * tint.rgb * (1.1 + 1.4 * fres) + env * env * 0.25 * fres;
	return vec4(min(col, vec3(1.0)), 1.0);
}
