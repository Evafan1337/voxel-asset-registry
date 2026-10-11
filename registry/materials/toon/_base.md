---
id: toon
title: Процедурный toon
shader: toon
inherits: null
generator_version: 1
complexity_level: 2
tags: [toon, stylized, npr]
preview: [assets/mt_truck/v005, components/vh_truck/v005, components/vh_heli_light/v005]
params:
  bands: {type: int, default: 3, min: 1, max: 6, description: число ступеней света (1 — плоская заливка)}
  softness: {type: float, default: 0.02, min: 0.0, max: 0.25, description: мягкость границ ступеней}
  band_bias: {type: float, default: 0.0, min: -0.4, max: 0.4, description: 'сдвиг порогов: + светлее,
      − темнее'}
  shadow_color: {type: color, default: '#3b4270', description: цвет тени (умножается на альбедо)}
  shadow_strength: {type: float, default: 0.55, min: 0.0, max: 1.0, description: насколько тень уходит
      в shadow_color}
  light_tint: {type: color, default: '#fff6e8', description: оттенок освещённой стороны}
  specular: {type: float, default: 0.25, min: 0.0, max: 1.0}
  specular_size: {type: float, default: 0.12, min: 0.0, max: 0.5}
  rim: {type: float, default: 0.2, min: 0.0, max: 1.0, description: контровой свет по краю силуэта}
  rim_width: {type: float, default: 0.3, min: 0.05, max: 0.8}
  rim_color: {type: color, default: '#ffffff'}
  halftone: {type: float, default: 0.0, min: 0.0, max: 1.0, description: комикс-точки в тени (экранные)}
  halftone_scale: {type: float, default: 6.0, min: 3.0, max: 16.0, description: 'шаг растра, пиксели'}
  outline_mode:
    type: enum
    default: hull
    values: [none, hull, screen]
    description: hull — вывернутая оболочка; screen — детектор краёв по глубине/нормалям
  outline_width: {type: float, default: 0.012, min: 0.0, max: 0.05, description: 'толщина hull-контура,
      м'}
  outline_px: {type: float, default: 1.5, min: 0.5, max: 4.0, description: 'толщина screen-контура, пиксели'}
  outline_color: {type: color, default: '#1c1b22'}
---
Процедурный toon-шейдер без текстур: всё задаётся параметрами. Одна и та же модель освещения
реализована трижды:

- `blender.py` — ноды Eevee (Shader to RGB) для превью в реестре; screen-контур через Freestyle;
- вьюер (three.js, GLSL) — живой предпросмотр со слайдерами;
- `toon.gdshader`, `toon_outline.gdshader`, `toon_screen_outline.gdshader` — для игры на Godot 4.

Модель (одинаковая во всех реализациях):

```
L     = saturate(N·Ldir) · shadow
x     = saturate(L + band_bias)
t     = bands == 1 ? 1 : Σ(k=1..bands−1) smoothstep(k/bands − s, k/bands + s, x) / (bands − 1),  s = softness
dark  = mix(1, shadow_color, shadow_strength)
shade = mix(dark, light_tint, t) · (halftone-точки в тени)
color = albedo · shade
      + light_tint · specular · smoothstep(th − s', th + s', N·H) · [L > 0],   th = 1 − specular_size/2
      + rim_color · rim · smoothstep(1 − rim_width − s', 1 − rim_width + s', 1 − |N·V|) · (0.35 + 0.65 t)
```

Альбедо — вершинные цвета модели из палитры. Контур: `hull` — оболочка, вывернутая наружу
на `outline_width` метров (сглаженные нормали, чтобы не рвалась на углах вокселей); `screen` —
постобработка по разрывам глубины и нормалей толщиной `outline_px`.
