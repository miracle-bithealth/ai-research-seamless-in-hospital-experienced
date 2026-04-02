import re


def inject_route_overlay(
    svg_str: str,
    points: list[tuple[float, float]],
    color: str = "#2563EB",
    stroke_width: float = 4.0,
) -> str:
    """Insert a polyline route overlay before </svg>. String ops only."""
    if not points:
        return svg_str

    points_str = " ".join(f"{x},{y}" for x, y in points)
    polyline = (
        f'<polyline points="{points_str}" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-dasharray="none" opacity="0.85" />'
    )
    return svg_str.replace("</svg>", f"{polyline}\n</svg>")


def inject_markers(
    svg_str: str,
    start_point: tuple[float, float],
    end_point: tuple[float, float],
    start_color: str = "#16A34A",
    end_color: str = "#DC2626",
    radius: float = 8.0,
) -> str:
    """Insert start (green) and end (red) circle markers before </svg>."""
    start_circle = (
        f'<circle cx="{start_point[0]}" cy="{start_point[1]}" '
        f'r="{radius}" fill="{start_color}" stroke="white" stroke-width="2" />'
    )
    end_circle = (
        f'<circle cx="{end_point[0]}" cy="{end_point[1]}" '
        f'r="{radius}" fill="{end_color}" stroke="white" stroke-width="2" />'
    )
    markers = f"{start_circle}\n{end_circle}"
    return svg_str.replace("</svg>", f"{markers}\n</svg>")


def inject_arrows(
    svg_str: str,
    points: list[tuple[float, float]],
    turn_indices: list[int],
    color: str = "#2563EB",
    size: float = 10.0,
) -> str:
    """Insert arrowhead polygons at turn points before </svg>."""
    if not turn_indices or len(points) < 2:
        return svg_str

    arrows = []
    for idx in turn_indices:
        if idx < 1 or idx >= len(points):
            continue
        bx, by = points[idx]
        ax, ay = points[idx - 1]

        # Direction vector from previous to current
        dx = bx - ax
        dy = by - ay
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0:
            continue
        dx /= length
        dy /= length

        # Arrow tip at current point, base perpendicular
        tip_x = bx + dx * size
        tip_y = by + dy * size
        left_x = bx - dy * (size / 2)
        left_y = by + dx * (size / 2)
        right_x = bx + dy * (size / 2)
        right_y = by - dx * (size / 2)

        arrow = (
            f'<polygon points="{tip_x},{tip_y} {left_x},{left_y} {right_x},{right_y}" '
            f'fill="{color}" />'
        )
        arrows.append(arrow)

    if not arrows:
        return svg_str

    arrows_str = "\n".join(arrows)
    return svg_str.replace("</svg>", f"{arrows_str}\n</svg>")


def inject_labels(
    svg_str: str,
    labels: list[dict],
    font_size: float = 12.0,
    color: str = "#1E293B",
) -> str:
    """Insert text labels before </svg>.

    labels: list of {"x": float, "y": float, "text": str}
    """
    if not labels:
        return svg_str

    elements = []
    for lbl in labels:
        x = lbl["x"]
        y = lbl["y"]
        text = lbl["text"]
        # Background rect for readability
        bg = (
            f'<rect x="{x - 2}" y="{y - font_size}" '
            f'width="{len(text) * font_size * 0.6 + 4}" height="{font_size + 4}" '
            f'fill="white" opacity="0.8" rx="2" />'
        )
        txt = (
            f'<text x="{x}" y="{y}" font-size="{font_size}" '
            f'fill="{color}" font-family="sans-serif">{text}</text>'
        )
        elements.append(f"{bg}\n{txt}")

    elements_str = "\n".join(elements)
    return svg_str.replace("</svg>", f"{elements_str}\n</svg>")


def crop_viewbox(
    svg_str: str,
    bbox: tuple[float, float, float, float],
) -> str:
    """Set the viewBox attribute on the root <svg> element.

    bbox: (min_x, min_y, width, height)
    """
    vb = f"{bbox[0]:.1f} {bbox[1]:.1f} {bbox[2]:.1f} {bbox[3]:.1f}"

    # Replace existing viewBox
    if "viewBox" in svg_str:
        svg_str = re.sub(
            r'viewBox="[^"]*"',
            f'viewBox="{vb}"',
            svg_str,
            count=1,
        )
    else:
        # Insert viewBox into the opening <svg> tag
        svg_str = svg_str.replace("<svg", f'<svg viewBox="{vb}"', 1)

    return svg_str


def inject_turn_badge(
    svg_str: str,
    point: tuple[float, float],
    direction: str,
    font_size: float = 14.0,
) -> str:
    """Insert a direction badge (e.g., 'BELOK ->') at a point before </svg>."""
    direction_labels = {
        "right": "BELOK KANAN ->",
        "left": "<- BELOK KIRI",
        "slight_right": "AGAK KANAN ->",
        "slight_left": "<- AGAK KIRI",
        "sharp_right": "BELOK KANAN ->",
        "sharp_left": "<- BELOK KIRI",
        "straight": "LURUS",
    }
    label = direction_labels.get(direction, direction.upper())
    x, y = point

    badge_width = len(label) * font_size * 0.55 + 12
    badge = (
        f'<rect x="{x - badge_width / 2}" y="{y - font_size - 4}" '
        f'width="{badge_width}" height="{font_size + 8}" '
        f'rx="4" fill="#1E40AF" opacity="0.9" />\n'
        f'<text x="{x}" y="{y}" text-anchor="middle" '
        f'font-size="{font_size}" fill="white" '
        f'font-family="sans-serif" font-weight="bold">{label}</text>'
    )
    return svg_str.replace("</svg>", f"{badge}\n</svg>")
