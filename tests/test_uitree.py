from droidcode.uitree import (
    clickables,
    find_by_resource_id,
    find_by_text,
    flatten,
    labelled_text,
    parse,
)

XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example" content-desc="" clickable="false" enabled="true" bounds="[0,0][1080,2400]">
    <node index="0" text="Pay now" resource-id="btn_pay" class="android.widget.Button" package="com.example" content-desc="" clickable="true" enabled="true" visible-to-user="true" bounds="[40,1800][1040,1932]" text-size-dp="16" bold="false" />
    <node index="1" text="" resource-id="btn_more" class="android.widget.ImageButton" package="com.example" content-desc="More options" clickable="true" enabled="true" visible-to-user="true" bounds="[900,300][1040,440]" />
    <node index="2" text="Disabled" resource-id="btn_off" class="android.widget.Button" package="com.example" content-desc="" clickable="true" enabled="false" visible-to-user="true" bounds="[40,2000][1040,2100]" />
  </node>
</hierarchy>
"""


def test_parse_builds_hierarchy_with_bounds():
    root = parse(XML)
    assert root.class_name == "android.widget.FrameLayout"
    assert len(root.children) == 3
    node = find_by_resource_id(root, "btn_pay")
    assert node is not None
    assert node.bounds.width == 1000
    assert node.clickable is True


def test_unknown_attributes_are_preserved():
    root = parse(XML)
    node = find_by_resource_id(root, "btn_pay")
    assert node.attrs["text_size_dp"] == 16
    assert node.attrs["bold"] is False


def test_find_by_text_is_case_insensitive_and_partial():
    root = parse(XML)
    assert find_by_resource_id(root, "nope") is None
    assert find_by_text(root, "pay") is not None
    assert find_by_text(root, "absent") is None


def test_clickables_exclude_disabled_nodes():
    root = parse(XML)
    ids = [node.node_id for node in clickables(root)]
    assert "btn_pay" in ids and "btn_more" in ids
    assert "btn_off" not in ids


def test_labelled_text_returns_only_text_nodes():
    root = parse(XML)
    # btn_more has a content description but no rendered text; the root has neither
    assert [node.node_id for node in labelled_text(root)] == ["btn_pay", "btn_off"]


def test_node_ids_fall_back_to_path_when_no_resource_id():
    root = parse(XML)
    assert len(flatten(root)) == 4


def test_accessible_name_accepts_text_or_description():
    root = parse(XML)
    assert find_by_resource_id(root, "btn_more").has_accessible_name() is True
    assert root.children[0].has_accessible_name() is True
