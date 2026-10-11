---
id: zk_axle
title: Żuk · управляемая ось и подвеска
type: structure
category: zuk_kit
inherits: null
generator_version: 2
complexity_level: 3
tags: [zuk, transport, modular, running_gear]
interface:
  grid_size: [12, 4, 5]
  voxel_size: 0.25
  pivot: ground
  mounts: [generic, ground]
  sockets:
    - {name: suspension_left, type: generic, position: [-0.625, 0.625, 0.0], description: "Неподвижный верхний якорь подвески под рамой"}
    - {name: suspension_right, type: generic, position: [0.625, 0.625, 0.0], description: "Неподвижный верхний якорь подвески под рамой"}
    - {name: suspension_inset_left, type: generic, position: [-0.375, 0.625, 0.0], description: "Верхний якорь подвески inset; исходный suspension_left сохраняется"}
    - {name: suspension_inset_right, type: generic, position: [0.375, 0.625, 0.0], description: "Верхний якорь подвески inset; исходный suspension_right сохраняется"}
design_intent:
  role: articulated_running_gear
  purpose: "Два переиспользуемых колеса, поворотные кулаки и независимый положительный ход подвески"
  primary_parts: [wheels, axle]
  secondary_parts: [suspension, steering, rims, hubs]
  relationships:
    - {type: touches_ground, part: wheels}
    - {type: symmetric, part: wheels, axis: x}
    - {type: attached_to, part: wheels, target: axle}
    - {type: attached_to, part: suspension, target: axle}
  forbidden: [orphan_geometry]
params:
  wheel_fit: {type: enum, default: legacy, values: [legacy, inset], description: "Legacy: X±1 / ширина 0,5; inset: X±0,75 / ширина 0,25; радиус и база неизменны"}
  stage: {type: int, default: 3, min: 1, max: 3, description: "1 коробки; 2 12-гранные колёса; 3 диск/шина, кулаки и связанная подвеска"}
  steering: {type: bool, default: true, description: "Поворот передних колёс вокруг Z; false для задней оси"}
  steer_deg: {type: float, default: 20.0, min: 0.0, max: 20.0, description: "Амплитуда параллельного поворота в инспекционном цикле"}
  bump: {type: float, default: 0.0625, min: 0.0, max: 0.0625, description: "Ход каждого колеса вверх от дороги; вниз под ground plane движения нет"}
  turns: {type: int, default: 2, min: 0, max: 4, description: "Полные обороты колёс за бесшовный цикл"}
  animate: {type: bool, default: true, description: "Движение только stage 3 / level 3; false сохраняет статическую rest pose"}
  finish: {type: bool, default: true, description: "Материалы резины/металла stage 3; false для нейтрального листа"}
---
Система координат набора — Blender X поперёк, Z вверх, перед −Y. Корень стоит
на дороге под серединой оси. Центры колёс X ±1 м, Z 0,375 м; статическая ширина
2,5 м, передние колёса в повороте ±20° требуют динамический габарит 2,726 м.
База грузовика задаётся двумя сокетами шасси, а не координатами этого компонента.

Три стадии используют одну геометрию `zk_wheel`: stage 1 коробки, stage 2
12-гранные колёса, stage 3 отдельные шина/диск/ступица. На stage 3 и level 3
экспортируется цикл `work`: suspension → steering (Z) → spin (X). Полуоси,
рычаги и амортизаторы поворачиваются и меняют длину по тем же функциям,
сохраняя оба соединения. Верхние опоры Z 0,625 м соединяются с рамой шасси.

`v003` — передняя ось с поворотом; `v004` — задняя без поворота; `v005` —
статическая передняя для сравнительных листов. Цикл проверяет диапазон поз,
он не является симуляцией движения по дороге или геометрией Аккермана.

`v006–v010` — отдельная ветка `wheel_fit: inset` от соответствующих
`v001–v005`. Центры колёс X ±0,75 м, ширина 0,25 м. Статическая ширина оси
1,75 м; максимальная ширина при ±20° 1,991438 м остаётся внутри кузова 2 м.
Радиус 0,375 м, высота центров, база, ход подвески и цикл сохранены.
Физические верхние опоры inset — X ±0,375 / Z 0,625; опорные блоки
доходят до X ±0,4375 и стыкуются с рельсами inset. Все четыре сокета имеют
стабильные координаты; профиль выбирает физическую опору, не перемещая API.
