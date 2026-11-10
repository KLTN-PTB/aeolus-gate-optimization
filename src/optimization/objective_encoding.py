"""Lossless decimal-to-integer objective coefficients for CP-SAT."""
from fractions import Fraction
from math import lcm

MAX_OBJECTIVE_INTEGER = (1 << 62) - 1


def encode_objective(reassignment, overflow, requested_scale=100):
    values = [Fraction(str(v)) for v in (reassignment, overflow)]
    scale = lcm(requested_scale, *(v.denominator for v in values))
    if scale > MAX_OBJECTIVE_INTEGER:
        raise ValueError("Objective weights require an unsafe integer scale; use fewer decimal places")
    coefficients = [v.numerator * (scale // v.denominator) for v in values]
    if any(c < 0 or c > MAX_OBJECTIVE_INTEGER for c in coefficients):
        raise ValueError("Objective coefficient exceeds the safe CP-SAT integer range")
    return scale, *coefficients
