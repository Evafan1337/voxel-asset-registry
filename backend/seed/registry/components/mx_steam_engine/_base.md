---
id: mx_steam_engine
title: Механизмы · паровая машина
type: part
category: mechanism
inherits: null
generator_version: 4
complexity_level: 3
tags: [mechanism, animated]
interface:
  grid_size: [20, 17, 9]
  voxel_size: 0.25
  pivot: bottom_center
  mounts: []
  sockets: []
design_intent:
  role: steam_engine
  purpose: "Горизонтальная паровая машина: поршень в разрезанном цилиндре толкает крейцкопф, шатун крутит кривошип и маховик"
  primary_parts: [base, cylinder, crosshead, conrod, crank, flywheel]
  secondary_parts: [valve_gear, governor, particles]
  relationships:
    - {type: attached_to, part: cylinder, target: base}
    - {type: attached_to, part: flywheel, target: crank}
    - {type: attached_to, part: conrod, target: crosshead}
    - {type: touches_ground, part: base}
  forbidden: [orphan_geometry]
params:
  size: {type: float, default: 1.0, min: 0.5, max: 1.0, description: "Масштаб всей машины (1 — цилиндр 1,1 м, маховик R 1,15 м)"}
  turns: {type: int, default: 2, min: 1, max: 3, description: "Оборотов вала за цикл work (4 с)"}
  spokes: {type: int, default: 8, min: 6, max: 10, description: "Спиц маховика"}
  cutaway: {type: bool, default: true, description: "Окно в цилиндре спереди: виден поршень с кольцами"}
  particles: {type: bool, default: true, description: "Выхлоп паром на каждой мёртвой точке, продувка цилиндра (уровень 3)"}
  color: {type: enum, default: paint_green, description: "Станина, крышки, шатун", values: [paint_green, paint_blue, signal_red, steel_dark, soot, rust, brick, paint_yellow]}
  accent: {type: enum, default: brass, description: "Сальники, бугели, подшипники", values: [brass, copper, steel, steel_dark]}
  metal: {type: enum, default: steel, description: "Крейцкопф, параллели, поршень", values: [steel, steel_dark, brass]}
  flywheel: {type: enum, default: paint_green, values: [paint_green, paint_blue, signal_red, steel_dark, soot, rust, paint_yellow]}
  base: {type: enum, default: stone_dark, description: "Фундамент", values: [stone, stone_dark, brick, steel_dark]}
---
Горизонтальная паровая машина набора `mechanism` — «сердце» цеха: стоит на полу фундаментом,
линия машины вдоль X (цилиндр слева, вал справа), вал уходит назад (+Y), маховик за кривошипом.

- **Цилиндр** в деревянной обшивке с латунными бандажами; спереди вырез — видно поршень с
  кольцами. Сверху сзади золотниковая коробка, паропровод с вентилем, сбоку выхлопная труба.
- **Поршень → шток → крейцкопф** скользят по параллелям; **шатун** передаёт ход на палец
  **дискового кривошипа** с противовесом; на валу **маховик** со спицами.
- **Парораспределение:** эксцентрик на валу (опережает кривошип на 120°) через эксцентриковую
  тягу двигает шток золотника.
- **Регулятор Уатта** на золотниковой коробке крутится с шарами.
- **Пар:** выхлоп из трубы на каждой мёртвой точке (машина двойного действия — 2 клуба за
  оборот), продувочные краны под цилиндром.

Кинематика одна на все детали: угол вала φ = 2π·turns·t, положение крейцкопфа и углы тяг
считаются точно, шатун и тяга не растягиваются.

Зазоры держатся весь цикл: параллели кончаются у кронштейна сразу за передней мёртвой точкой
крейцкопфа и разнесены так, что шатун (кривошип 0,32 м, шатун 1,6 м, наклон до 11,5°) проходит
между ними; поршень не доходит до крышек на 0,1 м, нижняя головка шатуна не выходит за диск
кривошипа. Проверка по кадрам GLB — `builder/motion_clearance.py`, тест `tests/test_motion_clearance.py`.
