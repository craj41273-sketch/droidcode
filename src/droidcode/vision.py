"""Screenshot analysis: colour sampling and region diffing.

Colour is never taken from the view hierarchy (Android does not expose it);
it is estimated from the rendered frame, the way a human or a design reviewer
would see it. That keeps the checks honest for themed, tinted, and
programmatically-drawn UI.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

from .protocol import Bounds, UiNode

Color = tuple[int, int, int]


def _dominant(colors: list[Color]) -> Color:
    counts: dict[Color, int] = {}
    for color in colors:
        counts[color] = counts.get(color, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def estimate_colors(image: Image.Image, bounds: Bounds) -> tuple[Color, Color]:
    """Estimate (background, foreground) for a node's box.

    Background is the modal colour inside the box. Foreground is the most
    frequent colour that is clearly different from the background - the text
    or icon ink.
    """
    box = (
        max(0, bounds.left),
        max(0, bounds.top),
        min(image.width, bounds.right),
        min(image.height, bounds.bottom),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return (255, 255, 255), (0, 0, 0)

    region = image.crop(box).convert("RGB")
    raw = region.tobytes()
    pixels = [tuple(raw[index : index + 3]) for index in range(0, len(raw), 3)]
    background = _dominant(pixels)

    def distance(color: Color) -> int:
        return sum(abs(a - b) for a, b in zip(color, background))

    ink = [c for c in pixels if distance(c) > 24]
    foreground = _dominant(ink) if ink else background
    return background, foreground


def node_colors(image: Image.Image, node: UiNode) -> tuple[Color, Color]:
    return estimate_colors(image, node.bounds)


def diff_ratio(before: Image.Image, after: Image.Image, threshold: int = 12) -> tuple[float, Bounds | None]:
    """Fraction of pixels that changed beyond `threshold`, and their bounding box."""
    if before.size != after.size:
        raise ValueError(f"size mismatch: {before.size} vs {after.size}")
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    mask = diff.point(lambda value: 255 if value > threshold else 0)
    changed = sum(1 for value in mask.tobytes() if value)
    total = mask.width * mask.height
    bbox = mask.getbbox()
    if bbox is None:
        return 0.0, None
    return changed / total, Bounds(bbox[0], bbox[1], bbox[2], bbox[3])


def save(image: Image.Image, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target
