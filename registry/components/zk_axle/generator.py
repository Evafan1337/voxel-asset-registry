"""Front and rear Zuk axles share reusable wheel and suspension helpers."""


def build(params):
    import zuk_wheels

    return zuk_wheels.build_axle(params)
