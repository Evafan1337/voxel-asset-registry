---
id: zuk_truck
title: Zuk · контролируемая эволюция фургона
type: structure
inherits: null
generator_version: 1
complexity_level: 3
tags: [zuk, transport, modular, impressor, stage3]
interface:
  grid_size: [12, 11, 20]
  voxel_size: 0.25
  pivot: bottom_center
  sockets: []
params: {}
slots:
  chassis: {socket: null, accepts: [zk_chassis], max_grid: [12, 11, 20]}
  cab: {socket: chassis.cab, accepts: [zk_cab], max_grid: [12, 11, 20]}
  body: {socket: chassis.body, accepts: [zk_body], max_grid: [12, 11, 20]}
  axle_front: {socket: chassis.axle_front, accepts: [zk_axle], max_grid: [12, 5, 6]}
  axle_rear: {socket: chassis.axle_rear, accepts: [zk_axle], max_grid: [12, 5, 6]}
  head_left: {socket: cab.head_left, accepts: [zk_lamp], max_grid: [2, 1, 2], required: false}
  head_right: {socket: cab.head_right, accepts: [zk_lamp], max_grid: [2, 1, 2], required: false}
  tail_left: {socket: body.tail_left, accepts: [zk_lamp], max_grid: [2, 1, 2], required: false}
  tail_right: {socket: body.tail_right, accepts: [zk_lamp], max_grid: [2, 1, 2], required: false}
composition:
  read_at_glance: Короткая высокая кабина с цельным лобовым стеклом, низкий нос и длинный закрытый кузов на двух осях.
  primary_mass: body
  massing_grid: [12, 11, 20]
  hero_feature: cab
  secondary_features: [axle_front, axle_rear]
  quiet_zones: []
  slot_zones: {cab: front, chassis: ground, axle_front: ground, axle_rear: ground, head_left: front, head_right: front, tail_left: back, tail_right: back}
  detail_budget:
    max_large_attachments: 4
    max_repeats_per_component: 4
    max_roof_density: 0.0
    max_front_density: 1.0
    min_empty_socket_ratio: 0.0
---
Три стадии выбранного листа A из `impressor/iterations/zuk_sheet_study`.
Это процедурное предложение дизайна по фотографии, а не обмер оригинального автомобиля.

| вариант | стадия | результат |
|---|---|---|
| v001 | 1 | кабина, низкий нос, закрытый кузов, рама и четыре кубических колеса |
| v002 | 2 | первые 10 уточнений D01–D10; серые поверхности |
| v003 | 3 A | ещё 10 уточнений D11–D20, компактная сервисная панель, материалы и движение колёс |
| v004 | 3 B | та же сборка, только более широкая сервисная панель |

Все компоненты используют один скелет `builder/zuklib.py`: Blender X вправо,
Z вверх, перед −Y; glTF X вправо, Y вверх, перед +Z. Колёсная база 2,75 м,
крыша кабины и кузова 2,50 м, кузов шириной 2,00 м. Номинальный габарит колёс
2,50 м; при повороте на 20° нужен больший динамический габарит внутри сетки 3,00 м.
В новом наборе ширина колеса 0,50 м и центры X ±1,00 м постоянны на всех стадиях.
Это явное уточнение исходного предложения с кубами шириной 0,75 м и центрами X ±0,875 м.

Кабина, кузов, рама, передний и задний колёсные узлы и четыре фонаря собираются
штатными сокетами без ручных `slot_offsets`. Чистые планы остаются в координатах
грузовика; экспорт кабины вычитает её монтажный якорь, который сборка восстанавливает.
Фонари стоят на фиксированных полосах кузова вне задних дверей.

Stage 3 и Registry level 3 — разные понятия: первая означает 20 групп уточнений,
вторая включает четырёхсекундную демонстрацию поворота, вращения и хода подвески.
Иерархия узлов и оси доступны в GLB/Blender; игровую физику и управление задаёт
принимающий проект. Все версии оставлены draft для выбора и дальнейшей итерации.

### Исправленная ветка арок и колеи

`v005` / `v006` / `v007` / `v008` — исправленные stage 1 / 2 / 3 A / 3 B.
Параметр компонентов `wheel_fit: inset` явно задаёт structural change: ширина
шины 0,25 м, центры X ±0,75 м, нижняя граница кузовных масс Z 0,50 м.
Сохранены крыша 2,50 м, радиус 0,375 м, оси и база 2,75 м, положение всех
окон и деталей. Колёса в покое имеют боковой отступ 0,125 м внутри борта.
Арки — реальные сквозные вырезы, а не серые панели: прямоугольные на stage 1
и с двумя диагональными плечами на stage 2/3. Более узкие лонжероны и верхние
опоры подвески расположены внутри полного поворотного габарита колёс.
Существующие варианты сохраняют исходную геометрию `wheel_fit: legacy`.
