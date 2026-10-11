---
id: vh_truck
title: Транспорт · грузовик-фургон (эволюция)
type: part
category: vehicle
inherits: null
generator_version: 5
complexity_level: 2
tags: [transport, evolution]
interface:
  grid_size: [12, 13, 24]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: []
  sockets: []
params:
  stage: {type: int, default: 5, min: 1, max: 5, description: "1 MASSING (крупные массы) · 2 SILHOUETTE · 3 STRUCTURE · 4 DETAIL · 5 GAME"}
  part: {type: enum, default: all, values: [all, cab, body, wheel, chassis], description: "all — машина целиком; иначе ключевой блок по центру: кабина с капотом, фургон, правое переднее колесо с подкрылком, топливный бак"}
  cab: {type: enum, default: paint_blue, description: "Кабина", values: [paint_blue, signal_red, paint_green, paint_yellow, olive, steel, plaster, signal_orange]}
  body: {type: enum, default: steel, description: "Фургон", values: [steel, plaster, paint_blue, olive, signal_red, stone]}
  trim: {type: enum, default: steel_dark, description: "Бампер, рамы, крепёж", values: [steel_dark, soot, steel, olive_dark]}
  stripe: {type: enum, default: signal_red, description: "Полоса на фургоне (стадия 5)", values: [signal_red, signal_blue, paint_yellow, signal_orange, soot]}
---
Грузовик-фургон семейства `transport` (префикс `vh_`) — «эволюция модели» по правилам блокаута
(`builder/blockout.py`, раздел «Blockout and refinement rules» в CLAUDE.md). Смотрит в −Y (фасад
glTF +Z), левый борт +X (там бак), стоит колёсами на z = 0. Генератор — чистый план из масс,
граней, регионов и портов; `vehlib.render` рисует его в Blender, тесты читают план без Blender.

Скелет (MACRO_GRID 0,25 м, общий для всех стадий):
- колёса R 0,5 м: `axle_front` (y −2,25) и `axle_rear` (y 1,5) на оси машины, `wheel_*` — центры
  колёс (x ±1); спарка сзади — на ширину колеса + DETAIL внутрь;
- рама 1 × 5,5 м на высоте 0,5–1; капот 2 × 1 м, кабина 2 × 1,25 × 1,5 м (пол на 1 м);
  фургон 2,5 × 3 × 1,75 м на подрамнике (пол на 1,25 м, `body_floor`);
- `front_mount` — низ передней грани капота: бампер и номер; `mirror_left/right` — верхние
  передние углы ванны кабины: кронштейны зеркал; `tank_mount` — правый бок рамы: бак.

| stage | что добавляется |
|---|---|
| 1 · MASSING | 7 масс: капот, кабина, фургон, рама, бак, две оси, колёса-блоки |
| 2 · SILHOUETTE | капот → клин, кабина → ванна + клин с наклонным лобовым, бампер, рама → лонжероны и рессоры, подрамник, зеркала на кронштейнах, восьмигранные колёса |
| 3 · STRUCTURE | стёкла в регионах граней (лобовое, боковые), двери, решётка и фары, подкрылки, спарка сзади, каркас фургона (стойки, обвязка) с филёнками на DETAIL внутри, бак-цилиндр, поперечины, задний брус с фонарями, брызговики-крылья |
| 4 · DETAIL | рамы по границам стёкол, ручки, планки решётки, дворники, верхние кронштейны зеркал, подножки, рёбра и задние двери с петлями, хомуты бака, отбойник, гайки колёс |
| 5 · GAME | козырёк с маркерами, антенна, номер, поворотники, маркеры фургона, полоса, запоры, брызговики, выхлоп, крышка бака |

Каркас фургона идёт по рёбрам массы stage 1, а филёнки утоплены на DETAIL: ни одна деталь не
лежит вровень с гранью другого цвета, повёрнутой в ту же сторону, — такие пары мерцают
(`builder/zfight.py`, тест `tests/test_zfight.py`).

Варианты выстроены цепочкой: v001 → v002 → … → v005, каждая стадия — наследник предыдущей
(`delta: {stage: N}`). Ключевые блоки для витрины (`part`) — наследники стадий 1, 3 и 5.
