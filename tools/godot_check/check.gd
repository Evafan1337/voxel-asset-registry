# Imports a registry GLB in Godot 4 the way a game would and prints one JSON line with what it found:
# skeleton bones, skinned meshes, animation clips, the rest-pose AABB (feet on the ground, scale).
# godot --headless --script check.gd -- <model.glb>
# Used by `python -m registry godot-check` (no window, no GPU needed).
extends SceneTree

func _collect(node: Node, out: Dictionary) -> void:
	if node is Skeleton3D:
		var sk: Skeleton3D = node
		for i in sk.get_bone_count():
			out.bones.append(sk.get_bone_name(i))
	if node is AnimationPlayer:
		var player: AnimationPlayer = node
		for name in player.get_animation_list():
			var anim := player.get_animation(name)
			out.clips[name] = {"length": anim.length, "loop": anim.loop_mode != Animation.LOOP_NONE,
							   "tracks": anim.get_track_count()}
	if node is ImporterMeshInstance3D or node is MeshInstance3D:
		var skinned: bool = node.skin != null
		out.meshes.append({"name": String(node.name), "skinned": skinned})
		var aabb: AABB = (node.mesh.get_mesh() if node is ImporterMeshInstance3D else node.mesh).get_aabb()
		var box: AABB = node.global_transform * aabb if node.is_inside_tree() else aabb
		out.aabb = box if out.aabb == null else (out.aabb as AABB).merge(box)
	for child in node.get_children():
		_collect(child, out)

func _init() -> void:
	var path: String = OS.get_cmdline_user_args()[0]
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(path, state)
	if err != OK:
		print(JSON.stringify({"ok": false, "error": "cannot load %s (%d)" % [path, err]}))
		quit(1)
		return
	var scene := doc.generate_scene(state)
	get_root().add_child(scene)
	var out := {"bones": [], "clips": {}, "meshes": [], "aabb": null}
	_collect(scene, out)
	var box: AABB = out.aabb if out.aabb != null else AABB()
	print(JSON.stringify({"ok": true, "bones": out.bones, "clips": out.clips, "meshes": out.meshes,
						  "aabb_min": [box.position.x, box.position.y, box.position.z],
						  "aabb_size": [box.size.x, box.size.y, box.size.z]}))
	quit(0)
