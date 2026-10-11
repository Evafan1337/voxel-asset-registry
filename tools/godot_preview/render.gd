# Renders registry GLBs with a registry material (.tres) in Godot and saves a PNG.
# godot --path <proj> --script render.gd -- <out_png> <model.glb>[,...] <res://mat.tres|pbr> <outline_mode> <outline_px> <#outline>
# Used by `python -m registry godot-preview`; runs under xvfb-run (lavapipe Vulkan) without a window.
extends SceneTree

const SUN_DIR := Vector3(-0.45, 0.70, 0.55)   # toward the light (same as builder/preview.py)

func _initialize() -> void:
	_run.call_deferred()

func _run() -> void:
	await process_frame
	var args := OS.get_cmdline_user_args()
	var out_dir: String = args[0]
	var models: PackedStringArray = args[1].split(",")
	var mats: PackedStringArray = args[2].split(",")
	var root := Node3D.new()
	get_root().add_child(root)

	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.62, 0.63, 0.65)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0, 0, 0)
	e.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.environment = e
	root.add_child(env)

	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	root.add_child(sun)
	sun.look_at_from_position(Vector3.ZERO, -SUN_DIR.normalized(), Vector3.UP)

	var meshes: Array[MeshInstance3D] = []
	var x := 0.0
	var aabb := AABB()
	for path in models:
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file(path, state) != OK:
			push_error("cannot load " + path)
			continue
		var scene: Node3D = doc.generate_scene(state)
		root.add_child(scene)
		# characters carry several clips: show them posed in idle, never in the rest A-pose
		var player := scene.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if player != null and player.has_animation("idle"):
			player.play("idle")
			player.seek(0.5, true)
		await process_frame
		var found: Array[MeshInstance3D] = []
		_collect(scene, found)
		var box := AABB()
		var first := true
		for mi in found:
			var b: AABB = mi.global_transform * mi.get_aabb()
			box = b if first else box.merge(b)
			first = false
		scene.position.x = x - box.position.x
		scene.position.z = -(box.position.z + box.size.z / 2.0)
		x += box.size.x + 0.6
		meshes.append_array(found)
	for mi in meshes:
		var b: AABB = mi.global_transform * mi.get_aabb()
		aabb = b if aabb.size == Vector3.ZERO else aabb.merge(b)

	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = max(aabb.size.x, aabb.size.y) * 1.15
	var center := aabb.get_center()
	var dir := Vector3(1, 1, 1).normalized()
	root.add_child(cam)
	cam.look_at_from_position(center + dir * 30.0, center, Vector3.UP)
	cam.far = 100.0

	var quad := MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2(2, 2)
	quad.mesh = qm
	quad.extra_cull_margin = 16384
	var post := ShaderMaterial.new()
	post.shader = load("res://shaders/toon_screen_outline.gdshader")
	quad.material_override = post
	cam.add_child(quad)
	quad.position = Vector3(0, 0, -1)

	var mode: String = args[3] if args.size() > 3 else "none"
	var mat_path: String = mats[0]
	for mi in meshes:
		mi.material_override = null if mat_path == "pbr" else load(mat_path)
	quad.visible = mode == "screen"
	if quad.visible:
		post.set_shader_parameter("outline_px", float(args[4]))
		post.set_shader_parameter("outline_color", Color.html(args[5]))
	for i in 12:
		await process_frame
	get_root().get_texture().get_image().save_png(out_dir)
	print("saved ", out_dir)
	quit()

func _collect(n: Node, out: Array[MeshInstance3D]) -> void:
	if n is MeshInstance3D:
		var mi: MeshInstance3D = n
		# runtime glTF import turns "-colonly" hulls into plain meshes (no vertex colors) — hide them
		if (mi.mesh.surface_get_format(0) & Mesh.ARRAY_FORMAT_COLOR) == 0:
			mi.visible = false
		else:
			out.append(mi)
	for c in n.get_children():
		_collect(c, out)
