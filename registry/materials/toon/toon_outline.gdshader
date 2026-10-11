// Hull outline pass (use as next_pass of the toon material).
// Pushes back faces outward by outline_width meters. Voxel meshes are flat-shaded (split normals),
// so the builder stores smoothed normals octahedral-encoded in UV2; without UV2 it falls back to NORMAL.
shader_type spatial;
render_mode unshaded, cull_front, fog_disabled;

uniform float outline_width : hint_range(0.0, 0.05) = 0.012;
uniform vec3 outline_color : source_color = vec3(0.11, 0.106, 0.133);

vec3 oct_decode(vec2 e) {
	e = e * 2.0 - 1.0;
	vec3 n = vec3(e.xy, 1.0 - abs(e.x) - abs(e.y));
	float t = max(-n.z, 0.0);
	n.x += n.x >= 0.0 ? -t : t;
	n.y += n.y >= 0.0 ? -t : t;
	return normalize(n);
}

void vertex() {
	vec3 n = length(UV2) > 0.0 ? oct_decode(UV2) : NORMAL;
	VERTEX += n * outline_width;
}

void fragment() {
	ALBEDO = outline_color;
}
