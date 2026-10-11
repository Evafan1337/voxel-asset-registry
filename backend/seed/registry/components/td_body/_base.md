---
id: td_body
title: TD корпус
type: structure
category: td_hull
inherits: null
generator_version: 2
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [4, 7, 4]
  voxel_size: 0.25
  pivot: ground                # origin на земле под корпусом; корпус может висеть на высоте lift
  mounts: [roof]
  sockets:                     # номинально для box 0.44×0.5×0.32, lift 0
    - {name: weapon, type: surface, position: [0.0, 0.19, 0.24], description: "центр лицевой грани, +Z вперёд — ствол"}
    - {name: sensor, type: surface, position: [0.0, 0.23, 0.24], description: "лицевая грань выше центра — сенсор/глаз"}
    - {name: top, type: roof, position: [0.0, 0.32, 0.0], description: "крыша — ракетница, огонь"}
    - {name: bottom, type: surface, position: [0.0, 0.0, 0.0], description: "днище, +Z вниз — шип дрона"}
    - {name: side_left, type: surface, position: [-0.22, 0.19, 0.0], description: "−X, +Z наружу — броня, стабилизатор"}
    - {name: side_right, type: surface, position: [0.22, 0.19, 0.0]}
    - {name: leg_fl, type: leg, position: [-0.15, 0.0, 0.18], description: "бедро: +Z сокета вниз к стопе, +X наружу"}
    - {name: leg_fr, type: leg, position: [0.15, 0.0, 0.18]}
    - {name: leg_bl, type: leg, position: [-0.15, 0.0, -0.18]}
    - {name: leg_br, type: leg, position: [0.15, 0.0, -0.18]}
params:
  shape: {type: enum, default: box, values: [box, round], description: "box — рубленый корпус с фаской; round — гранёная сфера (дрон)"}
  width: {type: float, default: 0.44, min: 0.2, max: 1.0}
  depth: {type: float, default: 0.5, min: 0.2, max: 1.0}
  height: {type: float, default: 0.32, min: 0.12, max: 0.8}
  chamfer: {type: float, default: 0.07, min: 0.0, max: 0.2}
  taper: {type: float, default: 0.12, min: 0.0, max: 0.5}
  lift: {type: float, default: 0.0, min: 0.0, max: 0.9, description: "высота днища над землёй, м: у шагающих = leg_length ног, у дрона — высота парения"}
  palette_color: {type: enum, default: steel, values: [steel, steel_dark, stone, stone_dark]}
  trim_color: {type: enum, default: steel_dark, values: [steel_dark, soot, signal_orange, signal_blue, signal_red], description: "пояс/днище — цвет класса (башни синий, враги красный)"}
---
Универсальный механический корпус: голова башни (lift 0) и корпус врага (lift = длина ног
или высота парения). Pivot `ground`: точка отсчёта всегда на земле, поэтому ассет врага
ставится прямо на путь.

Ноги крепятся к `leg_*` у углов днища. Сокет смотрит `+Z` вниз, к стопе, а `+X` наружу, к
колену. `leg_length` ноги должен быть равен `lift` корпуса.
