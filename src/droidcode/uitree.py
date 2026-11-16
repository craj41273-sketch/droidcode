"""Parse and query an Android view/accessibility hierarchy.

`adb shell uiautomator dump` produces the XML this module reads. Unknown
attributes are preserved in `UiNode.attrs`, which is how optional signals
(`text_size_dp`, `corner_radius_dp`, `token`) travel from backends that can
supply them - a Compose semantics dump or a Paparazzi render, for example.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .protocol import Bounds, UiNode

_CLICKABLE = {"true": True, "false": False}


def _parse_bounds(raw: str) -> Bounds:
    """Parse uiautomator's `[left,top][right,bottom]` form."""
    raw = (raw or "").strip()
    if not raw.startswith("[") or "][" not in raw:
        return Bounds(0, 0, 0, 0)
    first, second = raw.split("][")
    left, top = (int(v) for v in first.strip("[").split(","))
    right, bottom = (int(v) for v in second.strip("]").split(","))
    return Bounds(left, top, right, bottom)


def _attr(element: ET.Element, name: str) -> str:
    return element.get(name, "") or ""


def _extras(element: ET.Element) -> dict[str, object]:
    known = {
        "index", "text", "resource-id", "class", "package", "content-desc",
        "clickable", "enabled", "focused", "selected", "checked", "scrollable",
        "bounds", "visible-to-user", "password", "rotation",
    }
    extras: dict[str, object] = {}
    for key, value in element.attrib.items():
        if key in known:
            continue
        normalised = key.replace("-", "_")
        extras[normalised] = _coerce(value)
    return extras


def _coerce(value: str) -> object:
    if value in ("true", "false"):
        return value == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def parse(xml_text: str) -> UiNode:
    """Return the hierarchy root."""
    root_element = ET.fromstring(xml_text)
    node = root_element.find("node")
    if node is None:
        raise ValueError("hierarchy contains no <node> element")
    return _convert(node, path="0")


def _convert(element: ET.Element, path: str) -> UiNode:
    resource_id = _attr(element, "resource-id")
    class_name = _attr(element, "class")
    node_id = resource_id or f"{class_name or 'node'}#{path}"
    node = UiNode(
        node_id=node_id,
        class_name=class_name,
        resource_id=resource_id,
        text=_attr(element, "text"),
        content_desc=_attr(element, "content-desc"),
        bounds=_parse_bounds(_attr(element, "bounds")),
        clickable=_CLICKABLE.get(_attr(element, "clickable"), False),
        enabled=_CLICKABLE.get(_attr(element, "enabled"), True),
        visible=_CLICKABLE.get(_attr(element, "visible-to-user"), True),
        attrs=_extras(element),
    )
    for index, child in enumerate(element.findall("node")):
        node.children.append(_convert(child, path=f"{path}.{index}"))
    return node


def find_by_text(root: UiNode, needle: str) -> UiNode | None:
    needle = needle.casefold()
    for node in root.walk():
        if needle in (node.text or "").casefold():
            return node
    return None


def find_by_resource_id(root: UiNode, resource_id: str) -> UiNode | None:
    for node in root.walk():
        if node.resource_id == resource_id:
            return node
    return None


def clickables(root: UiNode) -> list[UiNode]:
    return [n for n in root.walk() if n.clickable and n.visible and n.enabled]


def labelled_text(root: UiNode) -> list[UiNode]:
    """Nodes that render text and therefore carry contrast requirements."""
    out = []
    for node in root.walk():
        if node.visible and (node.text or "").strip():
            out.append(node)
    return out


def flatten(root: UiNode) -> list[UiNode]:
    return list(root.walk())
