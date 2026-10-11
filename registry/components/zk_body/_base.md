---
id: zk_body
title: Żuk · закрытый грузовой кузов
type: structure
category: zuk_kit
inherits: null
generator_version: 6
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
  - name: tail_left
    type: vehicle_lamp
    position:
    - -0.875
    - 1.125
    - -2.25
    rotation:
    - -90.0
    - 0.0
    - 0.0
  - name: tail_right
    type: vehicle_lamp
    position:
    - 0.875
    - 1.125
    - -2.25
    rotation:
    - -90.0
    - 0.0
    - 0.0
design_intent:
  role: zk_body
  purpose: Żuk · закрытый грузовой кузов
  primary_parts:
  - cargo
  secondary_parts:
  - rear_doors
  - rear_handles
  - rear_hinges
  - side_ribs
  - service_panels
  - arch_liners
  - arch_caps
  relationships: []
  forbidden:
  - orphan_geometry
  - decorative_supports
params:
  arch_balance:
    type: enum
    default: open
    values: [open, mini_cap, liner_only]
    description: open сохраняет прежнюю геометрию; mini_cap и liner_only добавляют подкрылок и меньшее горло со стадии 2, отличаются только наружной накладкой
  wheel_fit:
    type: enum
    default: legacy
    values: [legacy, inset]
    description: legacy сохраняет исходную геометрию; inset опускает боковины до Z0.5 и открывает сквозные арки
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
  service_panel:
    type: enum
    default: compact
    values:
    - compact
    - wide
    description: 'Одна верхняя служебная панель на каждом борту: ширина 0.5 либо 1
      м'
---
Закрытый кузов на общем якоре грузовика (0,0,0). Размер исходной массы 2×2.75×1.75 м; крыша Z=2.5 совпадает с кабиной. Стадия 2 делает настоящие квадратные проёмы над задними колёсами и пару задних дверных контуров. Двери заканчиваются внутри X±0.703125, а полосы фонарей стоят снаружи на X±0.875; фонари приходят через tail_left/right. Стадия 3 добавляет две ручки, четыре петли, ровно три горизонтальных ребра на каждом борту и по одному служебному контуру. service_panel:wide удваивает только ширину этого контура вдоль кузова; положение, высота и остальные детали сохранены.

Ветка wheel_fit=inset опускает нижние боковины до Z0.5 и создаёт настоящий сквозной проём Y=1.5±0.5 по всей ширине X, с верхом Z1.0. Стадия 1 — только прямоугольные коробки; стадии 2–3 имеют плечи-фаски 0.1875 под 45°. В проёме нет центральной массы, закрывающей боковую ортопроекцию. Крыша, двери, петли, ручки, рёбра, служебные панели и сокеты остаются на прежних мировых координатах; compact/wide изменяет только ширину панели.

Низкие наружные юбки Z0.5..0.75 занимают только X±0.5..1; центральный пол Z≥0.75 оставляет карман для рамы. Ни кузов, ни юбки не заполняют сквозной колёсный проём.

arch_balance действует только вместе с wheel_fit=inset. На стадии 1 новая ветка сохраняет макро-проём Y=1.5±0.5/Z1 и закрывает его внутреннюю верхнюю часть двумя коробчатыми подкрылками X±0.25..0.5/Z0.75..1. Со стадии 2 общее с кабиной горло Y=1.5±0.4375/Z0.875 получает фаски 0.125, тёмную внутреннюю стенку, переднюю/заднюю щёки и потолок. Подкрылок не заполняет ход колеса и касается оставшейся оболочки. mini_cap имеет небольшую наружную бровь с двумя короткими плечами под 45° и реальным верхним мостом; liner_only отличается только отсутствием этой накладки. Накладка начинается со стадии 2. Все исходные массы, двери, фонари, рёбра, панели и сокеты остаются на прежних местах; open/legacy не меняют геометрию.
