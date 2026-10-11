// Screen-space outline: put on a MeshInstance3D with a 2×2 QuadMesh (flip_faces off) as a child of
// the Camera3D; extra_cull_margin = 16384. Draws lines where depth or normals change sharply.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D normal_tex : hint_normal_roughness_texture, filter_nearest;
uniform float outline_px : hint_range(0.5, 4.0) = 1.5;
uniform vec3 outline_color : source_color = vec3(0.11, 0.106, 0.133);
uniform float depth_threshold = 0.02;
uniform float normal_threshold = 0.45;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float linear_depth(vec2 uv, mat4 inv_proj) {
	float d = texture(depth_tex, uv).r;
	vec4 view = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
	return -view.z / view.w;
}

void fragment() {
	vec2 px = outline_px / VIEWPORT_SIZE;
	vec2 offs[4] = vec2[](vec2(px.x, 0.0), vec2(-px.x, 0.0), vec2(0.0, px.y), vec2(0.0, -px.y));
	float d0 = linear_depth(SCREEN_UV, INV_PROJECTION_MATRIX);
	vec3 n0 = texture(normal_tex, SCREEN_UV).xyz * 2.0 - 1.0;
	float edge = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 uv = SCREEN_UV + offs[i];
		float d = linear_depth(uv, INV_PROJECTION_MATRIX);
		vec3 n = texture(normal_tex, uv).xyz * 2.0 - 1.0;
		edge = max(edge, step(depth_threshold * d0, abs(d - d0)));
		edge = max(edge, step(normal_threshold, 1.0 - dot(n0, n)));
	}
	ALBEDO = outline_color;
	ALPHA = edge;
}
