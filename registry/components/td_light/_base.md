---
id: td_light
title: TD световой акцент
type: part
category: td_light
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [4, 1, 2]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [roof, surface]
  sockets: []
params:
  shape: {type: enum, default: block, values: [block, strip, orb]}
  size: {type: float, default: 0.07, min: 0.03, max: 0.2}
  length: {type: float, default: 0.3, min: 0.05, max: 1.0, description: "длина полосы (shape: strip)"}
  color: {type: enum, default: signal_orange, values: [signal_orange, signal_blue, signal_red, paint_yellow, glass]}
---
Маленький яркий акцент на тёмной площадке: блок, полоса или шар. В blockout это
«emissive»-метка класса (оранжевая — общая конструкция, синяя — башня, красная — враг),
в игре — место для настоящего источника света.
