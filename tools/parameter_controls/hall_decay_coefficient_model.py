"""Reference arithmetic for the observed HALL decay raw-coefficient helper.

This maps the internal byte passed to the helper to the observed coefficient
GPR group. It deliberately does not map the LCD value (0..99) to that byte.
"""


def _signed32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def coefficient_registers(raw_coefficient: int) -> dict[int, int]:
    if not 0 <= raw_coefficient <= 0x7F:
        raise ValueError("raw coefficient must be a 7-bit nonnegative value")
    # OS 3.53 preserves the raw parameter in GPR 6E and GPR 5B's low
    # byte, but clamps the quadratic coefficient path at 12 and 76.
    coefficient = min(76, max(12, raw_coefficient))
    d2 = coefficient << 8
    d3 = _signed32(-d2)
    # 68000 MULS.W multiplies signed low words into a 32-bit result.
    product = _signed32(_signed16(d2) * _signed16(d3))
    d5 = _signed32(product + 0x3FFFFFFF)
    arithmetic_shifted = d5 >> 7
    gpr03 = (d2 << 8) & 0xFFFFFF
    # The upper byte of 5B is 8 through raw 119, then counts down to zero
    # through raw 127. This is directly measured across the full raw path.
    parameter_tag = min(8, 127 - raw_coefficient)
    return {
        0x03: gpr03,
        0x04: (-gpr03) & 0xFFFFFF,
        0x05: arithmetic_shifted & 0xFFFFFF,
        0x5B: ((parameter_tag << 16) | raw_coefficient) & 0xFFFFFF,
        0x6E: (raw_coefficient << 16) & 0xFFFFFF,
    }
