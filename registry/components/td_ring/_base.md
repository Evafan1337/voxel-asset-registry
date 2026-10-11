---
id: td_ring
title: TD энергокольцо
type: part
category: td_ring
inherits: null
generator_version: 1
complexity_level: 1
tags: [tower_defence, blockout]
interface:
  grid_size: [5, 1, 5]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: [roof]
  sockets: []
params:
  radius: {type: float, default: 0.34, min: 0.15, max: 0.6, description: "внешний радиус, м"}
  tube: {type: float, default: 0.06, min: 0.03, max: 0.12, description: "ширина обода"}
  height: {type: float, default: 0.07, min: 0.03, max: 0.15}
  segments: {type: int, default: 12, min: 6, max: 16}
  spokes: {type: int, default: 3, min: 0, max: 4, description: "спицы к ступице на оси (0 — обод без ступицы)"}
  hub_radius: {type: float, default: 0.1, min: 0.04, max: 0.2}
  palette_color: {type: enum, default: signal_blue, values: [signal_blue, steel, steel_dark, signal_orange]}
---
Горизонтальное кольцо со ступицей и спицами. Ставится на `collar` мачты: ступица надета
на ось, обод — крупный читаемый силуэт support-башни (BUFF / ENERGY).
