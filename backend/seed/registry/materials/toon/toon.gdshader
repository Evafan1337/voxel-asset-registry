// Procedural toon — Godot 4 implementation (Voxel Asset Registry, materials/toon).
// Same model as blender.py and the web viewer; parameters come from a registry variant (.tres).
// Scene setup: one DirectionalLight3D (energy 1) with shadows; keep ambient light low —
// the dark band is produced here, ambient only lifts it.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

uniform int bands : hint_range(1, 6) = 3;
uniform float softness : hint_range(0.0, 0.25) = 0.02;
uniform float band_bias : hint_range(-0.4, 0.4) = 0.0;
uniform vec3 shadow_color : source_color = vec3(0.231, 0.259, 0.439);
uniform float shadow_strength : hint_range(0.0, 1.0) = 0.55;
uniform vec3 light_tint : source_color = vec3(1.0, 0.965, 0.91);
uniform float specular : hint_range(0.0, 1.0) = 0.25;
uniform float specular_size : hint_range(0.0, 0.5) = 0.12;
uniform float rim : hint_range(0.0, 1.0) = 0.2;
uniform float rim_width : hint_range(0.05, 0.8) = 0.3;
uniform vec3 rim_color : source_color = vec3(1.0);
uniform float halftone : hint_range(0.0, 1.0) = 0.0;
uniform float halftone_scale : hint_range(3.0, 16.0) = 6.0;

void fragment() {
	ALBEDO = COLOR.rgb;   // palette vertex colors (glTF COLOR_0)
}

float toon_bands(float x) {
	if (bands <= 1) {
		return 1.0;
	}
	float s = max(softness, 1e-4);
	float acc = 0.0;
	for (int k = 1; k < bands; k++) {
		float b = float(k) / float(bands);
		acc += smoothstep(b - s, b + s, x);
	}
	return acc / float(bands - 1);
}

void light() {
	float L = clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION;
	float t = toon_bands(clamp(L + band_bias, 0.0, 1.0));
	vec3 dark = mix(vec3(1.0), shadow_color, shadow_strength);
	vec3 shade = mix(dark, light_tint, t);
	if (halftone > 0.0) {
		vec2 cell = fract(FRAGCOORD.xy / halftone_scale) - 0.5;
		float radius = sqrt(1.0 - t) * 0.7 * halftone;
		float inside = 1.0 - smoothstep(radius - 0.05, radius + 0.05, length(cell));
		shade *= 1.0 - 0.55 * inside;
	}
	vec3 light_rgb = LIGHT_COLOR / PI;   // LIGHT_COLOR is pre-multiplied by PI in Godot 4
	DIFFUSE_LIGHT += shade * light_rgb;

	float s2 = softness * 0.5 + 0.005;
	if (specular > 0.0 && L > 0.01) {
		float ndh = dot(NORMAL, normalize(LIGHT + VIEW));
		float th = 1.0 - specular_size * 0.5;
		SPECULAR_LIGHT += light_tint * specular * smoothstep(th - s2, th + s2, ndh) * light_rgb;
	}
	if (rim > 0.0) {
		float edge = smoothstep(1.0 - rim_width - s2, 1.0 - rim_width + s2, 1.0 - abs(dot(NORMAL, VIEW)));
		SPECULAR_LIGHT += rim_color * rim * edge * (0.35 + 0.65 * t) * light_rgb;
	}
}
