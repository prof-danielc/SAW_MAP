"""Integration tests decoding the post-tile records of the shipped game maps."""

from collections import Counter
from pathlib import Path

import pytest

from saw_map.diagnostics.records_report import format_records_report
from saw_map.formats.map_reader import MapReader
from saw_map.formats.record_layout import (
    TABLE_INFO_ITEMS,
    TABLE_ITEMS,
    TABLE_SOLDIER_POSITIONS,
    TABLE_SOLDIERS,
    TABLE_TOKENS,
    TABLE_WINDOW,
)
from saw_map.maps.entities import (
    ENTRY_CONDITION_NAMES,
    FLAG_INFO,
    FLAG_SOLDIER,
    FLAG_TOKEN,
    GERMAN_CHARACTER_TYPES,
)
from saw_map.maps.records import DecodeStatus, EntityCategory, decode_cell_index

GAME_DIR = Path("Research/SSI/Soldiers at War")
AIRFIELD = GAME_DIR / "Single_g" / "Airfield.map"
DEMO = GAME_DIR / "Menu" / "Demo.MAP"

# Frame counts of the built-in archives (People.obj, Token.obj, Can.obj, Turret.obj)
ARCHIVE_FRAMES = {"People": 168, "Token": 44, "Can": 64, "Turret": 320}

pytestmark = pytest.mark.skipif(not AIRFIELD.is_file(), reason="Game assets not found")


@pytest.fixture(scope="module")
def all_maps():
    """Parses every shipped map once."""
    paths = sorted(p for p in GAME_DIR.rglob("*") if p.suffix.lower() == ".map")
    assert paths
    return [(path, MapReader.parse_map(path)) for path in paths]


def test_every_v21_map_is_consumed_exactly(all_maps):
    """SC-001 / SC-002: all bytes after the tile array are assigned to tables; all maps load."""
    statuses = Counter()
    for path, doc in all_maps:
        post = doc.post_tile
        assert post is not None, path.name
        statuses[(doc.version, post.status)] += 1
        if doc.version == "21":
            assert post.status == DecodeStatus.DECODED, f"{path.name}: {post.status_detail}"
            assert sum(t.layout.byte_size for t in post.tables) == post.byte_size == 31366
            assert post.tables[0].offset == post.start_offset == 1183193
            for table in post.tables:
                assert len(table.records) == table.layout.slot_count
                assert all(len(r.raw) == table.layout.record_size for r in table.records)
        assert doc.cells, path.name

    assert statuses[("21", DecodeStatus.DECODED)] == 95
    assert statuses[("19", DecodeStatus.UNSUPPORTED_VERSION)] == 1


def test_stored_window_matches_declared_dimensions(all_maps):
    """The playable window stored in the stream equals the centered mission-file window."""
    for path, doc in all_maps:
        if doc.version != "21":
            continue
        values = doc.post_tile.get_table(TABLE_WINDOW).records[0].values
        assert (values["min_x"], values["min_y"]) == (doc.origin_x, doc.origin_y), path.name
        assert (values["max_x"], values["max_y"]) == (doc.origin_x + doc.width, doc.origin_y + doc.height)

        mission_lines = MapReader._read_mission_lines(path)
        declared = MapReader._declared_dimensions(mission_lines)
        assert declared == (doc.width, doc.height), path.name
        assert doc.origin_x == (130 - doc.width) // 2 and doc.origin_y == (100 - doc.height) // 2


def test_placements_resolve_across_all_maps(all_maps):
    """SC-004: placements reference valid sprite frames; anomalies are rare and listed."""
    placed = anomalous = 0
    by_category = Counter()
    for path, doc in all_maps:
        for entity in doc.entities:
            by_category[entity.category] += 1
            if entity.sprite_archive is not None:
                assert entity.sprite_frame < ARCHIVE_FRAMES[entity.sprite_archive], (path.name, entity)
            if entity.category in (EntityCategory.SOLDIER, EntityCategory.TOKEN, EntityCategory.INFO):
                placed += 1
                anomalous += bool(entity.anomalies)

    assert by_category[EntityCategory.SOLDIER] > 1500
    assert by_category[EntityCategory.TOKEN] > 1000
    assert by_category[EntityCategory.INFO] > 400
    assert by_category[EntityCategory.TURRET] > 0
    assert anomalous / placed < 0.05


def test_record_cells_match_engine_cell_flags(all_maps):
    """Token and info item cells equal the cells the engine flags for drawing them."""
    for path, doc in all_maps:
        if doc.version != "21":
            continue
        post = doc.post_tile
        for table_id, mask in ((TABLE_TOKENS, FLAG_TOKEN), (TABLE_INFO_ITEMS, FLAG_INFO)):
            record_cells = {r.values["cell"] for r in post.get_table(table_id).used_records}
            in_window = {c for c in record_cells if doc.contains(c[0], c[1])}
            flagged = {key for key, cell in doc.cells.items() if cell.flags & mask}
            assert in_window == flagged, f"{path.name} {table_id}"

        # Every soldier inside the window stands on a cell carrying the soldier flag,
        # and so does every alternate (relocation) cell
        for record in post.get_table(TABLE_SOLDIER_POSITIONS).used_records:
            for field_name in ("cell", "alternate_cell"):
                position = record.values[field_name]
                cell = doc.get_cell(*position) if position is not None else None
                if cell is not None:
                    assert cell.flags & FLAG_SOLDIER, f"{path.name} soldier slot {record.slot_index} {field_name}"


def test_reinforcement_and_loadout_references(all_maps):
    """Reinforcement nationality pairs with the token frame; loadouts index in-use item slots."""
    frame_to_nationality = {7: 1, 8: 2, 9: 4}
    for path, doc in all_maps:
        if doc.version != "21":
            continue
        post = doc.post_tile
        for entity in doc.entities:
            if entity.category == EntityCategory.TOKEN:
                assert entity.attributes["nationality"] == frame_to_nationality[entity.sprite_frame], path.name
                assert 0 <= entity.attributes["percentage"] <= 100
                assert entity.attributes["ai"] in ("Seeker", "Wander"), path.name
                assert entity.attributes["entry_condition"] in ENTRY_CONDITION_NAMES, path.name
                if entity.attributes["nationality"] == 2:
                    assert entity.attributes["character_type"] in GERMAN_CHARACTER_TYPES, path.name
                if entity.attributes["entry_condition"] in ("Target Eliminate", "Target Get"):
                    assert entity.attributes["turn_or_token"] == 0, path.name

        # Information tokens: the target matches its type, and the lists cover every stored value
        tokens = post.get_table(TABLE_INFO_ITEMS)
        positions = post.get_table(TABLE_SOLDIER_POSITIONS)
        for record in tokens.used_records:
            values = record.values
            assert values["condition"] <= 4 and values["causes"] <= 3, path.name
            if values["target_type"] == 0:
                assert decode_cell_index(values["target"]) == values["cell"], path.name
            elif values["target_type"] == 5:
                assert positions.records[values["target"]].in_use, path.name
            else:
                assert values["target_type"] == 9, path.name
                assert post.get_table(TABLE_ITEMS).records[values["target"]].in_use, path.name

        items = post.get_table(TABLE_ITEMS)
        soldiers = post.get_table(TABLE_SOLDIERS)
        for record in post.get_table(TABLE_SOLDIER_POSITIONS).used_records:
            for word in soldiers.records[record.slot_index].values["loadout"]:
                if word != 0xFFFF:
                    item = items.records[word]
                    assert item.in_use, f"{path.name} soldier slot {record.slot_index}"
                    # An item in a loadout names that soldier as its holder
                    assert (item.values["holder_type"], item.values["holder"]) == (5, record.slot_index), path.name

        # Every item is held by a soldier (5) or a canister (0); canister items sit on canister cells
        for item in items.used_records:
            assert item.values["holder_type"] in (0, 5), path.name
        for entity in doc.entities:
            if entity.category == EntityCategory.ITEM and doc.contains(entity.x, entity.y):
                assert not entity.anomalies, (path.name, entity)


def test_soldier_field_ranges_and_frame_formula(all_maps):
    """Soldier fields stay inside the editor's dropdown lists; the sprite frame follows appearance and facing."""
    total = matching = 0
    for path, doc in all_maps:
        if doc.version != "21":
            continue
        post = doc.post_tile
        soldiers = post.get_table(TABLE_SOLDIERS)
        for record in post.get_table(TABLE_SOLDIER_POSITIONS).used_records:
            data = soldiers.records[record.slot_index].values
            if data["nationality"] == 0xFFFF:  # one blank soldier record exists in the shipped maps
                continue
            assert data["nationality"] in (1, 2, 4, 8, 16), path.name
            assert data["controller"] in (0, 1), path.name
            assert data["rank"] <= 18 and data["ai"] <= 7, path.name
            assert data["primary_training"] <= 6 and data["secondary_training"] <= 6, path.name
            assert data["facing"] <= 7 and data["appearance"] <= 20, path.name
            assert data["field_medic"] in (0, 1), path.name
            # Portrait numbers stay inside Portrait.obj (287 frames, three per portrait)
            assert data["portrait"] == 0xFFFF or 3 * data["portrait"] < 287, path.name
            total += 1
            matching += record.values["frame"] == 8 * data["appearance"] + (data["facing"] + 4) % 8

    assert total > 1800
    assert matching / total > 0.98


def test_airfield_reference_placements():
    """SC-003: decoded placements agree with the Scenario Builder screenshots of Airfield."""
    doc = MapReader.parse_map(AIRFIELD)
    counts = Counter(e.category for e in doc.entities)
    assert counts[EntityCategory.SOLDIER] == 40
    assert counts[EntityCategory.RELOCATION] == 13
    assert counts[EntityCategory.TOKEN] == 32  # "GermanTokens 32" in airfield_reinforcement_token_2.png
    assert counts[EntityCategory.INFO] == 2
    assert not any(e.anomalies for e in doc.entities)

    # The soldier beside the Ju 52 in airfield_airplane.png (cursor cell 45, 42, 0)
    (guard,) = [e for e in doc.entities_at(44, 41, 0) if e.category == EntityCategory.SOLDIER]
    assert (guard.sprite_archive, guard.sprite_frame) == ("People", 88)
    assert guard.attributes["nationality"] == 2

    # The 8 attackers form one group at the south-east corner
    soldiers = [e for e in doc.entities if e.category == EntityCategory.SOLDIER]
    attackers = [e for e in soldiers if e.attributes["nationality"] == 1]
    assert [e.slot_index for e in attackers] == list(range(8))
    assert all(87 <= e.x <= 95 and 63 <= e.y <= 70 for e in attackers)

    # Dice tokens of airfield_dices_1..3.png: alternate positions of soldiers 16, 22, 23
    dice = {(e.x, e.y, e.z): e.attributes["soldier"] for e in doc.entities if e.category == EntityCategory.RELOCATION}
    assert dice[(51, 42, 0)] == 16 and dice[(56, 25, 0)] == 22 and dice[(69, 50, 0)] == 23

    # Character ID 23 (airfield_dices_3_character.png): German, Computer, 100 %, encumbrance 30
    character = next(e for e in soldiers if e.slot_index == 23)
    assert character.attributes["alternate_cell"] == (69, 50, 0)
    assert (character.attributes["nationality"], character.attributes["controller"]) == (2, "Computer")
    assert (character.attributes["percentage"], character.attributes["encumbrance"]) == (100, 30)
    assert character.attributes["ai"] == "Guard" and character.attributes["field_medic"] is False
    # Portrait 80: the face shown in airfield_dices_3_character_outfitting.png is Portrait.obj frame 240
    assert character.attributes["portrait"] == "Portrait.obj:240"

    # Rank and training of four characters as shown by the editor's Character Stats dialog
    # (rank, primary, secondary, AI or None, facing or None)
    expected = {
        (37, 24, 0): ("Lt Colonel", "Pistol", "Submachinegun", "Stationary", "S"),
        (36, 23, 0): ("Sgt Major", "Submachinegun", "Semi/Automatic", None, "SE"),
        (38, 27, 0): ("Staff Sgt", "Semi/Automatic", "Pistol", None, "SW"),
        (90, 38, 0): ("Senior Sgt", "Bolt Action", "Submachinegun", "Guard", None),
    }
    for cell, (rank, primary, secondary, ai, facing) in expected.items():
        (soldier,) = [e for e in doc.entities_at(*cell) if e.category == EntityCategory.SOLDIER]
        attributes = soldier.attributes
        assert (attributes["rank"], attributes["primary"], attributes["secondary"]) == (rank, primary, secondary), cell
        if ai is not None:
            assert attributes["ai"] == ai, cell
        if facing is not None:
            assert attributes["facing"] == facing, cell

    # Reinforcement token at (75, 88, 0) (airfield_reinforcement_token_2.png): amount 1, 50 %
    (token,) = [e for e in doc.entities_at(75, 88, 0) if e.category == EntityCategory.TOKEN]
    assert token.label == "German reinforcement"
    assert token.attributes == {
        "nationality": 2, "amount": 1, "character_type": "SS Infantry", "percentage": 50, "controller": "Computer",
        "ai": "Seeker", "entry_condition": "Target Eliminate", "turn_or_token": 0,
    }

    # Ammo at (76, 14, 0) (airfield_ammo.png) and the folder at (92, 67, 0) (airfield_folder_1.png)
    assert Counter(e.category for e in doc.entities_at(76, 14, 0)) == {EntityCategory.ITEM: 2, EntityCategory.CANISTER: 1}
    assert [e.category for e in doc.entities_at(92, 67, 0)] == [EntityCategory.INFO]

    # Mission exit cells of airfield_information_token.png (level 1, south-east corner)
    exits = {(e.x, e.y, e.z) for e in doc.entities if e.label == "mission exit"}
    assert {(115, y, 1) for y in range(84, 89)} | {(x, 88, 1) for x in range(108, 115)} <= exits
    assert len(exits) == 27

    # The inactive turret group is decoded but hidden, as in the editor
    turrets = [e for e in doc.entities if e.category == EntityCategory.TURRET]
    assert len(turrets) == 9 and all(e.attributes["hidden"] for e in turrets)

    # The objective cell (35, 25, 0) of airfield_objective_1..4.png: a canister holding the
    # "Map" item, and information token 3 ("Target Get" / "One Goal Met", radius 0) with its popup text
    at_goal = {e.category: e for e in doc.entities_at(35, 25, 0)}
    assert set(at_goal) == {EntityCategory.INFO, EntityCategory.ITEM, EntityCategory.CANISTER}
    objective = at_goal[EntityCategory.INFO]
    assert objective.slot_index == 3 and objective.label == "information token 3"
    assert objective.attributes["assigned"] == "Item" and objective.attributes["target"] == 56
    assert (objective.attributes["condition"], objective.attributes["causes"]) == ("Target Get", "One Goal Met")
    assert objective.attributes["radius"] == 0
    assert objective.attributes["message"].startswith("Searching through the office you stumble upon the map")
    assert at_goal[EntityCategory.ITEM].slot_index == 56  # the item slot the token's target refers to
    assert at_goal[EntityCategory.ITEM].label == "item in canister (class 5, kind 7)"
    assert at_goal[EntityCategory.CANISTER].attributes["items"] == 1

    # All five canisters of Airfield hold items; the "ammo" of airfield_ammo.png holds two
    canisters = {(e.x, e.y, e.z): e.attributes["items"] for e in doc.entities if e.category == EntityCategory.CANISTER}
    assert canisters == {(76, 14, 0): 2, (46, 20, 0): 3, (35, 25, 0): 1, (30, 34, 0): 4, (65, 36, 0): 2}
    assert counts[EntityCategory.ITEM] == 12

    # Information token 0, among the player's soldiers, carries the mission notebook text
    (notebook,) = [e for e in doc.entities_at(92, 67, 0) if e.category == EntityCategory.INFO]
    assert notebook.slot_index == 0 and notebook.attributes["radius"] == 15
    assert notebook.attributes["assigned"] == "Cell" and notebook.attributes["target"] == (92, 67, 0)
    assert (notebook.attributes["condition"], notebook.attributes["causes"]) == ("None", "None")
    assert notebook.attributes["message"].startswith("You open up your notebook")

    # The briefing is line 41 of the mission file, separate from the 40 token messages
    assert len(doc.token_messages) == 40
    assert doc.mission_text.startswith("We recovered plans at Cherbourg")


def test_records_report_and_demo_fallback():
    """The text report lists every table; the version 19 map loads with records unsupported."""
    doc = MapReader.parse_map(AIRFIELD)
    report = format_records_report(doc)
    assert report.startswith("POST-TILE DATA: Airfield (version 21)")
    assert "Status: DECODED | offset 1183193 | 31366 bytes | 19 tables | 0 bytes unassigned" in report
    for table in doc.post_tile.tables:
        assert f"[{table.layout.table_id}]" in report
    assert "SOLDIER       (44, 41, 0)  People.obj:88" in report
    assert "(unused)" not in report
    assert "(unused)" in format_records_report(doc, include_unused=True)

    demo = MapReader.parse_map(DEMO)
    assert demo.post_tile.status == DecodeStatus.UNSUPPORTED_VERSION
    assert (demo.width, demo.height, demo.origin_x, demo.origin_y) == (78, 60, 26, 20)
    assert len(demo.cells) == 78 * 60 * 7
    demo_report = format_records_report(demo)
    assert "UNSUPPORTED_VERSION" in demo_report and "version 19" in demo_report
