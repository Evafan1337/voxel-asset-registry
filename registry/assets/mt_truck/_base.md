---
id: mt_truck
title: Модульный грузовик
type: structure
inherits: null
generator_version: 1
complexity_level: 2
tags: [modular_truck, transport, modular, showcase]
interface:
  grid_size: [12, 14, 32]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
# Every block docks on the chassis socket of the same name: the road under its mount point
# (builder/trucklib.py, ANCHORS). The blocks are built at truck heights around that anchor.
slots:
  chassis: {socket: null, accepts: [mt_chassis], max_grid: [12, 14, 32]}
  cab: {socket: chassis.cab, accepts: [mt_cabin], max_grid: [12, 14, 32]}
  box: {socket: chassis.box, accepts: [mt_cargo_box], max_grid: [12, 14, 32]}
  axle_front: {socket: chassis.axle_front, accepts: [mt_wheelset], max_grid: [12, 14, 32]}
  axle_rear_1: {socket: chassis.axle_rear_1, accepts: [mt_wheelset], max_grid: [12, 14, 32]}
  axle_rear_2: {socket: chassis.axle_rear_2, accepts: [mt_wheelset], max_grid: [12, 14, 32]}
  exhaust: {socket: chassis.exhaust, accepts: [mt_exhaust], max_grid: [12, 14, 32], required: false}
  tank: {socket: chassis.tank, accepts: [mt_tank], max_grid: [12, 14, 32], required: false}
  toolbox: {socket: chassis.toolbox, accepts: [mt_toolbox], max_grid: [12, 14, 32], required: false}
---
Модульный грузовик-фургон — эксперимент «модульного набора блоков» по референсам Modular Cargo
Truck v1–v3: та же база, всё больше деталей, затем материалы. Три оси (передняя и тандем со
спаренными колёсами), кабина с капотом, фургон, выхлоп, бак и ящик на левом борту.

Блоки — компоненты `mt_*` (категория `truck_kit`), каждый — план блокаута со стадиями 1–5.
Варианты ассета — одна стадия на все блоки:

| вариант | stage | что видно |
|---|---|---|
| v001 | 1 · MASSING | рама, кабина и капот, фургон, восьмигранные колёса, колонна выхлопа, блоки бака и ящика |
| v002 | 2 · SILHOUETTE | клин кабины, бампер, зеркала, лонжероны и рессоры, подрамник, труба выхлопа |
| v003 | 3 · STRUCTURE | тонированное стекло, решётка, жёлтые фары, подкрылки, каркас фургона, обод — референс v1 |
| v004 | 4 · DETAIL | рамы, маркеры, подножки, швы, полосы катафотов, двери, хомуты, гайки — референс v2 |
| v005 | 5 · GAME | материалы: хром, тёмный металл, резина, стекло, светящиеся огни, катафоты — референс v3 |

Материалы — классы поверхностей палитры (`registry/palette.yaml` → `surfaces`): грани цвета
`metal_steel` получают материал `voxel_metal`, `lamp_*` — `voxel_light` и т. д.
