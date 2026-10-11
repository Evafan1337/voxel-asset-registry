---
id: zk_chassis
title: Żuk · рама и общие якоря
type: structure
category: zuk_kit
inherits: null
generator_version: 4
complexity_level: 2
tags:
- zuk
- transport
- sheet_study
- modular
interface:
  grid_size:
  - 12
  - 11
  - 20
  voxel_size: 0.25
  pivot: ground
  mounts:
  - generic
  sockets:
  - name: cab
    type: generic
    position:
    - 0.0
    - 0.0
    - 1.25
  - name: body
    type: generic
    position:
    - 0.0
    - 0.0
    - 0.0
  - name: axle_front
    type: generic
    position:
    - 0.0
    - 0.0
    - 1.25
  - name: axle_rear
    type: generic
    position:
    - 0.0
    - 0.0
    - -1.5
design_intent:
  role: zk_chassis
  purpose: Żuk · рама и общие якоря
  primary_parts:
  - chassis
  secondary_parts:
  - front_bumper
  - rear_bumper
  - steps
  relationships: []
  forbidden:
  - orphan_geometry
  - decorative_supports
params:
  wheel_fit:
    type: enum
    default: legacy
    values: [legacy, inset]
    description: legacy сохраняет исходную раму; inset использует узкие лонжероны X±0.375..0.4375
  stage:
    type: int
    default: 3
    min: 1
    max: 3
    description: 'Учебный процесс: 1 крупные массы · 2 первые 10 групп · 3 следующие
      10 групп'
  paint:
    type: enum
    default: paint_gray
    values:
    - paint_gray
    - olive
    description: Окраска на стадии 3; стадии 1 и 2 всегда нейтральные
  finish:
    type: bool
    default: true
    description: Материальные роли на стадии 3; false сохраняет нейтральную подачу
---
Рама определяет общий якорь и две оси, колёсная база 2.75 м. Стадия 1 — исходная коробка X±0.75, Y±2.25, Z0.5–0.75. Стадии 2–3 сохраняют её общий габарит, но заменяют сплошную массу двумя узкими лонжеронами и тремя поперечинами вне колёсного хода; возле осей край рамы не выходит за X±0.5625. D09/D10 — интегрированные передний и задний бамперы. На стадии 3 D18 даёт две короткие подножки сразу за передними проёмами: внутренний край касается лонжерона, дополнительных опор нет. Сокеты cab/body и axle_front/rear — одинаковые фиксированные якоря на всех стадиях.

Ветка wheel_fit=inset сохраняет якоря. Стадия 1 — один блок X±0.5 с прежними Y/Z на MACRO_GRID, который не пересекает неподвижные колёса. Стадии 2–3 уточняют его в две узкие коробчатые балки X±0.375..0.4375 и три поперечины X±0.5 вне колёсных проёмов, на DETAIL_GRID. Скруглений и фасок у рамы нет. Подножки на стадии 3 доходят внутренними краями до X±0.4375 и входят в специальные открытые ниши кабинного хоста. Ветка legacy геометрически не изменена.

В inset бамперы вынесены за торцы боковин: передний Y[-2.3125,-2.25], задний Y[2.25,2.3125], с прежними X/Z. Они касаются торцевых граней противоположными нормалями, не перекрывают их площади. Центральный пол хостов Z≥0.75 оставляет раме свободный карман.
