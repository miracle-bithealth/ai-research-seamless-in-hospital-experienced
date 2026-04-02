import math


def cross_product(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Cross product of vectors AB and BC.

    SVG Y-axis is inverted: positive = RIGHT turn, negative = LEFT turn.
    """
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def angle_between(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Signed angle in degrees at point B between segments AB and BC.

    Uses atan2 of cross product and dot product.
    Positive = right turn, negative = left turn (SVG coords).
    """
    ab = (b[0] - a[0], b[1] - a[1])
    bc = (c[0] - b[0], c[1] - b[1])

    cross = ab[0] * bc[1] - ab[1] * bc[0]
    dot = ab[0] * bc[0] + ab[1] * bc[1]

    if dot == 0 and cross == 0:
        return 0.0

    return math.degrees(math.atan2(cross, dot))


def classify_turn(angle: float) -> str:
    """Classify a signed angle into a turn direction label."""
    abs_angle = abs(angle)

    if abs_angle < 15:
        return "straight"

    if angle > 0:
        if abs_angle < 45:
            return "slight_right"
        if abs_angle < 135:
            return "right"
        return "sharp_right"
    else:
        if abs_angle < 45:
            return "slight_left"
        if abs_angle < 135:
            return "left"
        return "sharp_left"


def bounding_box(
    points: list[tuple[float, float]],
    padding: float = 80.0,
) -> tuple[float, float, float, float]:
    """Compute bounding box (min_x, min_y, width, height) with padding."""
    if not points:
        return (0, 0, 0, 0)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x = min(xs) - padding
    min_y = min(ys) - padding
    max_x = max(xs) + padding
    max_y = max(ys) + padding

    return (min_x, min_y, max_x - min_x, max_y - min_y)
