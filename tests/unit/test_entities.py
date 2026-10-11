"""Unit tests for placed entity extraction, entity draw order, and entity overlays."""

import struct
from typing import Dict, Tuple

from saw_map.formats.record_layout import (
    TABLE_INFO_ITEMS,
    TABLE_ITEMS,
    TABLE_REINFORCEMENTS,
    TABLE_SOLDIER_ARRAYS,
    TABLE_SOLDIER_POSITIONS,
    TABLE_SOLDIERS,
    TABLE_TOKENS,
    TABLE_TURRET_GROUPS,
    get_layout,
)
from saw_map.formats.records_reader import RecordsReader
from saw_map.maps.entities import ANOMALY_NO_CELL_FLAG, ANOMALY_OUTSIDE_WINDOW, extract_entities
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument
from saw_map.maps.records import EntityCategory, PlacedEntity, encode_cell_index
from saw_map.rendering.draw_order import DrawOrderStrategy
from saw_map.viewer.camera import Camera
from saw_map.viewer.input_handler import InputAction, InputHandler
from saw_map.viewer.inspector import CellInspector
from saw_map.viewer.overlays import OverlayModel

NO_CELL = 0xFFFFFFFF


def empty_block() -> Dict[Tuple[str, int], bytes]:
    """Record patches that mark every cell-bearing slot of a version 21 block as unused."""
    patches: Dict[Tuple[str, int], bytes] = {}
    for slot in range(40):
        patches[(TABLE_INFO_ITEMS, slot)] = b"\xFF" * 18
        patches[(TABLE_TOKENS, slot)] = struct.pack("<IH", NO_CELL, 3)
        patches[(TABLE_SOLDIER_POSITIONS, slot)] = struct.pack("<IHHIH", NO_CELL, 0, 0xFFFF, NO_CELL, 0)
    for slot in range(500):
        patches[(TABLE_ITEMS, slot)] = b"\xFF" * 18
    return patches


def build_doc(patches: Dict[Tuple[str, int], bytes], cells: Dict[Tuple[int, int, int], MapCell]) -> MapDocument:
    """Builds a 104x80 map document with a synthetic post-tile block and given cells."""
    out = bytearray()
    for table in get_layout("21"):
        for slot in range(table.slot_count):
            out += patches.get((table.table_id, slot), bytes(table.record_size))
    messages = [""] * 40
    messages[2] = "You find the map."
    doc = MapDocument(
        title="Test", version="21", width=104, height=80, origin_x=13, origin_y=10, cells=cells,
        post_tile=RecordsReader.read(bytes(out), 0, "21"), token_messages=messages,
    )
    doc.set_entities(extract_entities(doc))
    return doc


def make_cell(x: int, y: int, z: int, flags: int = 0x001F0000) -> MapCell:
    empty = CellComponent.from_raw_word(ComponentType.CLUTTER, 0)
    return MapCell(
        x=x, y=y, z=z,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0x8182),
        left_wall=empty, right_wall=empty, clutter=empty, flags=flags,
    )


def soldier_record(
    nationality: int, controller: int = 0, ai: int = 1, encumbrance: int = 30, field_medic: int = 0
) -> bytes:
    head = struct.pack(
        "<HHHHIHHHHH4IH", nationality, 6, controller, ai, field_medic, 0, 3, 2, encumbrance, 5, 1, 0, 0, 11, 80
    )
    return head + bytes(384)


def turret_record(state: int, base_cell: Tuple[int, int, int], base_frame: int) -> bytes:
    head = struct.pack("<6H40s4H", state, 0, 0, 0, 0, 0, b"", 0, 0, 0, 0)
    parts = b""
    for i in range(9):
        cell = encode_cell_index(base_cell[0] + i % 3, base_cell[1] + i // 3, base_cell[2])
        parts += struct.pack("<IH", cell, base_frame + i)
    return head + parts + bytes(11 * 6)


def test_no_entities_from_unused_slots():
    """Unused slots produce no entities, and a map without placements stays empty."""
    doc = build_doc(empty_block(), {})
    assert doc.post_tile.is_decoded
    assert doc.entities == []
    assert doc.entities_at(20, 20, 0) == []


def test_soldier_token_info_extraction():
    """Soldiers, reinforcement tokens, and info items are decoded with position, sprite, and attributes."""
    patches = empty_block()
    patches[(TABLE_SOLDIER_POSITIONS, 17)] = struct.pack("<IHHIH", encode_cell_index(44, 41, 0), 0, 0xFFFF, NO_CELL, 88)
    patches[(TABLE_SOLDIERS, 17)] = soldier_record(nationality=2)
    percentages = [100] * 40
    percentages[17] = 50
    patches[(TABLE_SOLDIER_ARRAYS, 0)] = struct.pack("<40H", *percentages)
    patches[(TABLE_SOLDIER_POSITIONS, 3)] = struct.pack("<IHHIH", encode_cell_index(50, 50, 1), 1, 0xFFFF, NO_CELL, 3)
    patches[(TABLE_SOLDIERS, 3)] = soldier_record(nationality=1, controller=1, ai=7, encumbrance=26, field_medic=1)
    patches[(TABLE_TOKENS, 0)] = struct.pack("<IH", encode_cell_index(75, 88, 0), 8)
    patches[(TABLE_REINFORCEMENTS, 0)] = struct.pack("<9H", 2, 3, 50, 0, 5, 0, 0, 1, 0)
    patches[(TABLE_INFO_ITEMS, 2)] = struct.pack("<I5HI", 56, 9, 0, 0, 1, 3, encode_cell_index(35, 25, 0))
    cells = {
        (44, 41, 0): make_cell(44, 41, 0, flags=0x001F0020),   # bit 5: soldier
        (75, 88, 0): make_cell(75, 88, 0, flags=0x001F0400),   # bit 10: token
        (35, 25, 0): make_cell(35, 25, 0, flags=0x001F0080),   # bit 7: info item
    }
    doc = build_doc(patches, cells)

    by_category = {c: [e for e in doc.entities if e.category == c] for c in EntityCategory}
    assert len(by_category[EntityCategory.SOLDIER]) == 2
    assert len(by_category[EntityCategory.TOKEN]) == 1
    assert len(by_category[EntityCategory.INFO]) == 1

    # Deterministic order: info items, tokens, soldiers (stream order of their tables)
    assert [e.category for e in doc.entities] == [
        EntityCategory.INFO, EntityCategory.TOKEN, EntityCategory.SOLDIER, EntityCategory.SOLDIER
    ]

    (soldier,) = doc.entities_at(44, 41, 0)
    assert (soldier.sprite_archive, soldier.sprite_frame) == ("People", 88)
    assert soldier.label == "soldier 17 (German)"
    assert soldier.attributes == {
        "hidden": False, "nationality": 2, "controller": "Computer", "rank": "Senior Sgt", "ai": "Guard",
        "primary": "Bolt Action", "secondary": "Submachinegun", "encumbrance": 30, "field_medic": False,
        "facing": "SW", "portrait": "Portrait.obj:240", "appearance": 11, "percentage": 50,
    }
    assert soldier.slot_index == 17 and soldier.source == TABLE_SOLDIER_POSITIONS
    assert soldier.anomalies == []

    hidden = by_category[EntityCategory.SOLDIER][0]
    assert hidden.slot_index == 3 and hidden.attributes["hidden"] is True
    assert hidden.label == "soldier 3 (American)" and hidden.attributes["controller"] == "Human"
    assert hidden.attributes["ai"] == "Wander" and hidden.attributes["field_medic"] is True

    token = by_category[EntityCategory.TOKEN][0]
    assert (token.sprite_archive, token.sprite_frame, token.label) == ("Token", 8, "German reinforcement")
    assert token.attributes == {
        "nationality": 2, "amount": 1, "character_type": "SS Infantry", "percentage": 50,
        "controller": "Computer", "ai": "Seeker", "entry_condition": "Target Eliminate", "turn_or_token": 0,
    }
    info = by_category[EntityCategory.INFO][0]
    assert (info.x, info.y, info.z) == (35, 25, 0)
    assert (info.sprite_archive, info.sprite_frame, info.label) == ("Token", 5, "information token 2")
    # Record (56, 9, 0, 0, 1, 3, cell): item slot 56, Target Get, radius 0, One Goal Met; text from line 3
    assert info.attributes == {
        "assigned": "Item", "target": 56, "condition": "Target Get", "causes": "One Goal Met", "radius": 0,
        "message": "You find the map.",
    }
    heading, detail = OverlayModel.get_entity_lines([info])[0]
    assert heading == "INFO: information token 2"
    assert detail == (
        'Token.obj:5 | T-554A80[2] | assigned=Item target=56 condition=Target Get causes=One Goal Met radius=0'
        ' | "You find the map."'
    )


def test_soldier_alternate_position_yields_relocation_entity():
    """A soldier with an alternate cell also yields a dice entity (editor mode "Relocate Char.")."""
    patches = empty_block()
    patches[(TABLE_SOLDIER_POSITIONS, 23)] = struct.pack(
        "<IHHIH", encode_cell_index(90, 38, 0), 0, 0xFFFF, encode_cell_index(69, 50, 0), 89
    )
    patches[(TABLE_SOLDIERS, 23)] = soldier_record(nationality=2)
    cells = {
        (90, 38, 0): make_cell(90, 38, 0, flags=0x001F0020),
        (69, 50, 0): make_cell(69, 50, 0, flags=0x001F0020),
    }
    doc = build_doc(patches, cells)

    assert [e.category for e in doc.entities] == [EntityCategory.SOLDIER, EntityCategory.RELOCATION]
    soldier, dice = doc.entities
    assert soldier.attributes["alternate_cell"] == (69, 50, 0)
    assert (dice.x, dice.y, dice.z) == (69, 50, 0)
    assert (dice.sprite_archive, dice.sprite_frame) == ("Token", 11)
    assert dice.label == "alternate position of soldier 23"
    assert dice.attributes == {"soldier": 23, "soldier_cell": (90, 38, 0)}
    assert dice.anomalies == [] and dice.slot_index == 23

    # Both the soldier and its dice are drawn as placed entities
    drawn = [it.entity.category for it in DrawOrderStrategy.generate_render_list(doc) if it.entity]
    assert sorted(c.value for c in drawn) == ["RELOCATION", "SOLDIER"]


def test_anomalies_are_flagged_not_dropped():
    """Entities outside the window or without their cell flag stay listed with an anomaly."""
    patches = empty_block()
    patches[(TABLE_SOLDIER_POSITIONS, 0)] = struct.pack("<IHHIH", encode_cell_index(5, 5, 0), 0, 0xFFFF, NO_CELL, 1)
    patches[(TABLE_TOKENS, 0)] = struct.pack("<IH", encode_cell_index(30, 30, 0), 8)
    doc = build_doc(patches, {(30, 30, 0): make_cell(30, 30, 0)})  # token cell lacks bit 10

    outside = next(e for e in doc.entities if e.category == EntityCategory.SOLDIER)
    assert outside.anomalies == [ANOMALY_OUTSIDE_WINDOW]
    token = next(e for e in doc.entities if e.category == EntityCategory.TOKEN)
    assert token.anomalies == [ANOMALY_NO_CELL_FLAG]


def test_turret_groups_and_items():
    """Turret groups yield one entity per part; groups with a non-zero state are hidden."""
    patches = empty_block()
    patches[(TABLE_TURRET_GROUPS, 0)] = turret_record(0, (60, 40, 2), 271)
    patches[(TABLE_TURRET_GROUPS, 1)] = turret_record(1, (69, 55, 1), 221)
    # Item 56 lies in the canister on (35, 25, 0); item 1 is carried by soldier 20
    patches[(TABLE_ITEMS, 56)] = struct.pack("<HIHHHHI", 0, encode_cell_index(35, 25, 0), 0xFFFF, 5, 7, 0xFFFF, NO_CELL)
    patches[(TABLE_ITEMS, 1)] = struct.pack("<HIHHHHI", 5, 20, 0xFFFF, 3, 0, 0xFFFF, NO_CELL)
    doc = build_doc(patches, {(35, 25, 0): make_cell(35, 25, 0, flags=0x001F0010 | (48 << 12))})

    turrets = [e for e in doc.entities if e.category == EntityCategory.TURRET]
    assert len(turrets) == 18
    active = [e for e in turrets if e.attributes["group"] == 0]
    assert [e.sprite_frame for e in active] == list(range(271, 280))
    assert (active[4].x, active[4].y, active[4].z) == (61, 41, 2)
    assert all(e.attributes["hidden"] is False for e in active)
    assert all(e.attributes["hidden"] is True for e in turrets if e.attributes["group"] == 1)

    items = [e for e in doc.entities if e.category == EntityCategory.ITEM]
    assert len(items) == 1  # only the item held by a canister is placed on the map
    assert (items[0].x, items[0].y, items[0].sprite_archive, items[0].slot_index) == (35, 25, None, 56)
    assert items[0].label == "item in canister (class 5, kind 7)" and items[0].anomalies == []
    (canister,) = [e for e in doc.entities if e.category == EntityCategory.CANISTER]
    assert canister.attributes == {"items": 1}

    # Hidden turret parts are not drawn
    drawn = DrawOrderStrategy.generate_render_list(doc)
    assert sum(1 for it in drawn if it.entity and it.entity.category == EntityCategory.TURRET) == 9


def test_cell_flag_entities():
    """Ground objects and editor markers are derived from cell flags."""
    cells = {
        (20, 20, 0): make_cell(20, 20, 0, flags=0x001F0010 | (48 << 12)),      # bit 4, Can frame 48
        (21, 20, 0): make_cell(21, 20, 0, flags=0x001F0001),                    # mission exit
        (22, 20, 0): make_cell(22, 20, 0, flags=0x001F0200 | (3 << 24)),        # land mine + multiplayer marker 3
        (23, 20, 0): make_cell(23, 20, 0, flags=0x801F0000 | (5 << 28)),        # medical + area effect 5
        (24, 20, 0): make_cell(24, 20, 0),                                      # plain cell
    }
    doc = MapDocument(title="T", version="21", width=104, height=80, origin_x=13, origin_y=10, cells=cells)
    doc.set_entities(extract_entities(doc))

    (ground,) = doc.entities_at(20, 20, 0)
    assert ground.category == EntityCategory.CANISTER
    assert (ground.sprite_archive, ground.sprite_frame) == ("Can", 48 & 0x3F)

    assert [(e.label, e.sprite_frame) for e in doc.entities_at(21, 20, 0)] == [("mission exit", 6)]
    assert [(e.label, e.sprite_frame) for e in doc.entities_at(22, 20, 0)] == [("land mine", 4), ("multiplayer marker 3", 2)]
    assert [(e.label, e.sprite_frame) for e in doc.entities_at(23, 20, 0)] == [("medical", 10), ("area effect 5", 17)]
    assert doc.entities_at(24, 20, 0) == []


def entity_doc() -> MapDocument:
    cells = {(30, 30, 0): make_cell(30, 30, 0), (30, 30, 2): make_cell(30, 30, 2)}
    doc = MapDocument(title="T", version="21", width=104, height=80, origin_x=13, origin_y=10, cells=cells)
    doc.set_entities([
        PlacedEntity(EntityCategory.SOLDIER, 30, 30, 0, "T-554F60", 0, "soldier 0 (German)", "People", 88, {"hidden": False}),
        PlacedEntity(EntityCategory.TOKEN, 30, 30, 2, "T-559230", 1, "German reinforcement", "Token", 8),
        PlacedEntity(EntityCategory.MARKER, 30, 30, 0, "cell flags", -1, "mission exit", "Token", 6),
        PlacedEntity(EntityCategory.ITEM, 40, 40, 0, "T-892AD0", 0, "item"),
    ])
    return doc


def test_draw_order_entity_filters():
    """Entities sort after their cell's tile components and obey toggles and elevation filters."""
    doc = entity_doc()

    items = DrawOrderStrategy.generate_render_list(doc)
    kinds = [(it.grid_z, it.component_type, it.asset_name) for it in items]
    assert kinds == [
        (0, ComponentType.FLOOR, None),
        (0, ComponentType.ENTITY, "People"),
        (0, ComponentType.ENTITY, None),      # item without sprite -> placeholder marker
        (2, ComponentType.FLOOR, None),
        (2, ComponentType.ENTITY, "Token"),
    ]
    assert items[1].entity is doc.entities[0] and items[1].component is None
    assert items[1].sprite_frame_index == 88

    # Markers are off by default and independent of the entity toggle
    with_markers = DrawOrderStrategy.generate_render_list(doc, show_markers=True)
    assert sum(1 for it in with_markers if it.entity and it.entity.category == EntityCategory.MARKER) == 1
    no_entities = DrawOrderStrategy.generate_render_list(doc, show_entities=False, show_markers=True)
    assert [it.entity.category for it in no_entities if it.entity] == [EntityCategory.MARKER]

    # Terrain is unaffected by hiding entities
    assert [it for it in DrawOrderStrategy.generate_render_list(doc, show_entities=False) if it.entity] == []
    assert len(DrawOrderStrategy.generate_render_list(doc, show_entities=False)) == 2

    # Elevation filter and isolation apply to entities
    low = DrawOrderStrategy.generate_render_list(doc, max_layer=1)
    assert all(it.grid_z <= 1 for it in low) and any(it.entity for it in low)
    isolated = DrawOrderStrategy.generate_render_list(doc, isolated_layer=2)
    assert [it.asset_name for it in isolated if it.entity] == ["Token"]


def test_entity_toggles_inspection_and_overlays():
    """Entity toggles redraw; inspector, status bar, sidebar, and metadata expose entities."""
    cam = Camera()
    redraws = []
    handler = InputHandler(cam, on_redraw_needed=lambda: redraws.append(1))
    assert (cam.show_entities, cam.show_markers) == (True, False)
    handler.handle_action(InputAction.TOGGLE_ENTITIES)
    handler.handle_action(InputAction.TOGGLE_MARKERS)
    assert (cam.show_entities, cam.show_markers) == (False, True)
    assert len(redraws) == 2

    doc = entity_doc()
    info = CellInspector.inspect_cell(doc.get_cell(30, 30, 0), None, doc.entities_at(30, 30, 0))
    assert [e.category for e in info.entities] == [EntityCategory.SOLDIER, EntityCategory.MARKER]
    assert CellInspector.inspect_cell(doc.get_cell(30, 30, 0)).entities == ()

    lines = OverlayModel.get_entity_lines(info.entities)
    assert lines[0] == ("SOLDIER: soldier 0 (German)", "People.obj:88 | T-554F60[0] | hidden=False")
    assert lines[1] == ("MARKER: mission exit", "Token.obj:6 | cell flags")

    status = OverlayModel.get_status_bar_text(doc, Camera(), (30, 30, 0))
    assert "<soldier 0 (German)>" in status

    # A cell holding only an entity is pickable
    inspector = CellInspector()
    assert inspector._is_pickable(doc, 40, 40, 0) is True
    assert inspector._is_pickable(doc, 41, 40, 0) is False

    # Without post-tile data the metadata dialog says so instead of showing counts
    assert "No post-tile data loaded." in OverlayModel.get_map_metadata_lines(doc, None)
    decoded = build_doc(empty_block(), {})
    summary = OverlayModel.get_entity_summary_lines(decoded)
    assert summary[0].startswith("Soldiers: 0") and "Anomalies: 0" in summary[3]
