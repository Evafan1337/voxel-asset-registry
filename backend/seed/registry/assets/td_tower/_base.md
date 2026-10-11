---
id: td_tower
title: TD башня (база семейства)
abstract: true
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, tower, blockout]
interface:
  grid_size: [6, 8, 8]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
slots:
  base:
    socket: null
    accepts: [td_base]
    max_grid: [8, 2, 8]
    description: "основание — занимает 1 тайл"
  pedestal:
    socket: support
    accepts: [td_pedestal]
    max_grid: [3, 7, 3]
  beacon:
    socket: front
    accepts: [td_light]
    max_grid: [4, 1, 2]
    required: false
    description: "маркер на лицевой грани основания"
---
Башня Tower Defence: основание в 1 тайл, поворотный пьедестал, сверху «голова» класса.
Все башни — одна линейка: одинаковые основание, пьедестал и оранжевые полосы, отличаются
только верхом. Смотрят вперёд (+Z glTF) — стволы и пусковые панели направлены туда.
