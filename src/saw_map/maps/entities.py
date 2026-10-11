"""Extraction of placed entities from decoded post-tile tables and cell flags.

Turns raw records into PlacedEntity objects following the draw routines of the engine
(SAW_TD sub_435562 soldiers, sub_434FB0 tokens, sub_4352FD turret parts, sub_43505D
cell-flag markers). Names follow the Scenario Builder's own mode names (Character,
Relocate Char., Info, Item / Canister, A/G/N Reinforce, Mission Exit, Land Mine, ...).
Decoupled from all UI and rendering libraries.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from saw_map.formats.record_layout import (
    SOLDIER_ARRAY_PERCENTAGE,
    TABLE_INFO_ITEMS,
    TABLE_ITEMS,
    TABLE_REINFORCEMENTS,
    TABLE_SOLDIER_ARRAYS,
    TABLE_SOLDIER_POSITIONS,
    TABLE_SOLDIERS,
    TABLE_TOKENS,
    TABLE_TURRET_GROUPS,
    TURRET_PARTS_PER_GROUP,
)
from saw_map.maps.model import MapCell, MapDocument
from saw_map.maps.records import EntityCategory, PlacedEntity, PostTileData, decode_cell_index

# Built-in sprite archives (flat registry tail, see TilesetDefinition.get_all_assets)
ARCHIVE_PEOPLE = "People"
ARCHIVE_TOKEN = "Token"
ARCHIVE_CAN = "Can"
ARCHIVE_TURRET = "Turret"
ARCHIVE_PORTRAIT = "Portrait"

# Portrait.obj stores three frames per portrait number (normal, highlighted, darkened)
PORTRAIT_FRAMES_PER_ID = 3
NO_PORTRAIT = 0xFFFF

# Cell flag bits evaluated by sub_43505D / sub_4508F9 / sub_434FB0
FLAG_MISSION_EXIT = 1 << 0
FLAG_CANISTER = 1 << 4
FLAG_SOLDIER = 1 << 5
FLAG_INFO = 1 << 7
FLAG_LAND_MINE = 1 << 9
FLAG_TOKEN = 1 << 10
FLAG_LOCKABLE = 1 << 23
FLAG_MEDICAL = 1 << 31

TOKEN_FRAME_INFO = 5

# Item table holder types: who holds an item
ITEM_HOLDER_CANISTER = 0
ITEM_HOLDER_SOLDIER = 5

# Known People.obj body types (soldier 'appearance')
APPEARANCE_NAMES: Dict[int, str] = {15: "male civilian", 16: "female civilian"}
TOKEN_FRAME_RELOCATION = 11

# Nationality codes shared by soldiers and reinforcement tokens. The editor writes
# Token.obj frame 7 / 8 / 9 for its "A Reinforce" / "G Reinforce" / "N Reinforce" modes,
# and those frames pair with codes 1 / 2 / 4 in every shipped map.
NATIONALITY_LABELS: Dict[int, str] = {1: "American", 2: "German", 4: "Neutral", 8: "French", 16: "Italian"}

# Dropdown lists of the Scenario Builder's Character Stats dialog; the stored value is
# the list index (verified against four Airfield characters, see record_layout).
CONTROLLER_NAMES: Tuple[str, ...] = ("Computer", "Human")
RANK_NAMES: Tuple[str, ...] = (
    "Private", "1st Private", "Lance Cpl", "Sr Lance Cpl", "Corporal", "Sargeant", "Senior Sgt",
    "Sgt Major", "Staff Sgt", "2nd Lieutenant", "Lieutenant", "Captain", "Major", "Lt Colonel",
    "Brigadier", "Maj General", "Lt General", "General", "Col General",
)
AI_NAMES: Tuple[str, ...] = (
    "Follower", "Guard", "Hider", "Mach Gunner", "Medic", "Seeker", "Stationary", "Wander",
)
# Information token dialog lists
TOKEN_TARGET_TYPES: Dict[int, str] = {0: "Cell", 5: "Character", 9: "Item"}
TOKEN_CONDITION_NAMES: Tuple[str, ...] = ("None", "Target Get", "Target Eliminate", "Target Destination", "Trigger")
TOKEN_CAUSES_NAMES: Tuple[str, ...] = ("None", "Immediate Victory", "Immediate Defeat", "One Goal Met")

# Reinforcement dialog lists; the character type list shown is the one of German tokens
GERMAN_CHARACTER_TYPES: Tuple[str, ...] = ("Infantry", "Grenadier", "Officer", "SS Infantry", "SS Officer")
ENTRY_CONDITION_NAMES: Tuple[str, ...] = (
    "Target Eliminate", "Target Get", "Target Destination", "Sighted", "Trigger", "Turn Limit", "Condition",
)
NATIONALITY_GERMAN = 2

# Soldier facing as seen on screen (N = up); the sprite sub-frame is (facing + 4) % 8
FACING_NAMES: Tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
TRAINING_NAMES: Tuple[str, ...] = (
    "None", "Pistol", "Submachinegun", "Bolt Action", "Semi/Automatic", "Machinegun", "Explosive",
)
REINFORCEMENT_LABELS: Dict[int, str] = {
    7: "American reinforcement",
    8: "German reinforcement",
    9: "Neutral reinforcement",
}

ANOMALY_OUTSIDE_WINDOW = "outside playable window"
ANOMALY_NO_CELL_FLAG = "cell flag not set"

# (flag mask, Token.obj frame, label) for single-bit editor markers drawn by sub_43505D
_SINGLE_BIT_MARKERS: Tuple[Tuple[int, int, str], ...] = (
    (FLAG_MISSION_EXIT, 6, "mission exit"),
    (FLAG_LAND_MINE, 4, "land mine"),
    (FLAG_MEDICAL, 10, "medical"),
    (FLAG_LOCKABLE, 12, "lockable"),
)


def nationality_label(code: int) -> str:
    """Readable name of a nationality code."""
    return NATIONALITY_LABELS.get(code, f"nationality {code}")


def portrait_frame(portrait: int) -> int:
    """Portrait.obj frame of the normal picture of a portrait number."""
    return PORTRAIT_FRAMES_PER_ID * portrait


def list_name(names: Tuple[str, ...], index: int) -> str:
    """Name of a dropdown list entry, or the raw value when it is outside the list."""
    return names[index] if 0 <= index < len(names) else str(index)


def extract_entities(map_doc: MapDocument) -> List[PlacedEntity]:
    """Builds the placed entities of a map from its post-tile tables and cell flags.

    Entities are returned in a deterministic order: table entities in stream order
    (information tokens, reinforcement tokens, soldiers with their relocation cells,
    turret parts, items), then cell-flag entities by cell. Entities outside the playable
    window are kept and flagged as anomalies.

    Args:
        map_doc: Map document with cells and, optionally, decoded post-tile data.

    Returns:
        List of placed entities; table entities are omitted when the post-tile data
        was not decoded.
    """
    entities: List[PlacedEntity] = []
    post_tile = map_doc.post_tile
    if post_tile is not None and post_tile.is_decoded:
        entities.extend(_info_items(post_tile, map_doc))
        entities.extend(_tokens(post_tile, map_doc))
        entities.extend(_soldiers(post_tile, map_doc))
        entities.extend(_turret_parts(post_tile))
        entities.extend(_items(post_tile, map_doc))
    entities.extend(_cell_flag_entities(map_doc.cells.values()))

    # A canister lists how many items of the item table lie in it
    contents: Dict[Tuple[int, int, int], int] = {}
    for entity in entities:
        if entity.category == EntityCategory.ITEM:
            key = (entity.x, entity.y, entity.z)
            contents[key] = contents.get(key, 0) + 1
    for entity in entities:
        if entity.category == EntityCategory.CANISTER:
            entity.attributes["items"] = contents.get((entity.x, entity.y, entity.z), 0)

    for entity in entities:
        if not map_doc.contains(entity.x, entity.y):
            entity.anomalies.append(ANOMALY_OUTSIDE_WINDOW)
    return entities


def _flag_check(map_doc: MapDocument, cell: Tuple[int, int, int], mask: int) -> List[str]:
    """Returns an anomaly when a loaded cell lacks the flag the engine uses to draw the entity."""
    map_cell = map_doc.get_cell(*cell)
    if map_cell is not None and not map_cell.flags & mask:
        return [ANOMALY_NO_CELL_FLAG]
    return []


def _info_items(post_tile: PostTileData, map_doc: MapDocument) -> List[PlacedEntity]:
    table = post_tile.get_table(TABLE_INFO_ITEMS)
    if table is None:
        return []
    result: List[PlacedEntity] = []
    for record in table.used_records:
        cell = record.values["cell"]
        target_type = record.values["target_type"]
        attributes: Dict[str, Any] = {
            "assigned": TOKEN_TARGET_TYPES.get(target_type, str(target_type)),
            "target": decode_cell_index(record.values["target"]) if target_type == 0 else record.values["target"],
            "condition": list_name(TOKEN_CONDITION_NAMES, record.values["condition"]),
            "causes": list_name(TOKEN_CAUSES_NAMES, record.values["causes"]),
            "radius": record.values["radius"],
        }
        # The popup text of token N is line N + 1 of the companion mission file
        if record.slot_index < len(map_doc.token_messages) and map_doc.token_messages[record.slot_index]:
            attributes["message"] = map_doc.token_messages[record.slot_index]
        result.append(
            PlacedEntity(
                category=EntityCategory.INFO,
                x=cell[0],
                y=cell[1],
                z=cell[2],
                source=TABLE_INFO_ITEMS,
                slot_index=record.slot_index,
                label=f"information token {record.slot_index}",
                sprite_archive=ARCHIVE_TOKEN,
                sprite_frame=TOKEN_FRAME_INFO,
                attributes=attributes,
                anomalies=_flag_check(map_doc, cell, FLAG_INFO),
            )
        )
    return result


def _tokens(post_tile: PostTileData, map_doc: MapDocument) -> List[PlacedEntity]:
    table = post_tile.get_table(TABLE_TOKENS)
    if table is None:
        return []
    reinforcements = post_tile.get_table(TABLE_REINFORCEMENTS)
    result: List[PlacedEntity] = []
    for record in table.used_records:
        cell = record.values["cell"]
        frame = record.values["frame"]
        attributes: Dict[str, Any] = {}
        if reinforcements is not None:
            settings = reinforcements.records[record.slot_index].values
            character_type = settings["character_type"]
            attributes = {
                "nationality": settings["nationality"],
                "amount": settings["amount"],
                "character_type": (
                    list_name(GERMAN_CHARACTER_TYPES, character_type)
                    if settings["nationality"] == NATIONALITY_GERMAN
                    else character_type
                ),
                "percentage": settings["percentage"],
                "controller": list_name(CONTROLLER_NAMES, settings["controller"]),
                "ai": list_name(AI_NAMES, settings["ai"]),
                "entry_condition": list_name(ENTRY_CONDITION_NAMES, settings["entry_condition"]),
                "turn_or_token": settings["turn_or_token"],
            }
        result.append(
            PlacedEntity(
                category=EntityCategory.TOKEN,
                x=cell[0],
                y=cell[1],
                z=cell[2],
                source=TABLE_TOKENS,
                slot_index=record.slot_index,
                label=REINFORCEMENT_LABELS.get(frame, f"token (frame {frame})"),
                sprite_archive=ARCHIVE_TOKEN,
                sprite_frame=frame,
                attributes=attributes,
                anomalies=_flag_check(map_doc, cell, FLAG_TOKEN),
            )
        )
    return result


def _soldiers(post_tile: PostTileData, map_doc: MapDocument) -> List[PlacedEntity]:
    positions = post_tile.get_table(TABLE_SOLDIER_POSITIONS)
    if positions is None:
        return []
    soldiers = post_tile.get_table(TABLE_SOLDIERS)
    arrays = post_tile.get_table(TABLE_SOLDIER_ARRAYS)
    result: List[PlacedEntity] = []
    for record in positions.used_records:
        slot = record.slot_index
        cell = record.values["cell"]
        alternate: Optional[Tuple[int, int, int]] = record.values["alternate_cell"]
        attributes: Dict[str, Any] = {"hidden": bool(record.values["hidden"])}
        label = f"soldier {slot}"
        if soldiers is not None:
            data = soldiers.records[slot].values
            attributes["nationality"] = data["nationality"]
            attributes["controller"] = list_name(CONTROLLER_NAMES, data["controller"])
            attributes["rank"] = list_name(RANK_NAMES, data["rank"])
            attributes["ai"] = list_name(AI_NAMES, data["ai"])
            attributes["primary"] = list_name(TRAINING_NAMES, data["primary_training"])
            attributes["secondary"] = list_name(TRAINING_NAMES, data["secondary_training"])
            attributes["encumbrance"] = data["encumbrance"]
            attributes["field_medic"] = bool(data["field_medic"])
            attributes["facing"] = list_name(FACING_NAMES, data["facing"])
            if data["portrait"] != NO_PORTRAIT:
                attributes["portrait"] = f"{ARCHIVE_PORTRAIT}.obj:{portrait_frame(data['portrait'])}"
            appearance = data["appearance"]
            attributes["appearance"] = (
                f"{appearance} ({APPEARANCE_NAMES[appearance]})" if appearance in APPEARANCE_NAMES else appearance
            )
            label = f"soldier {slot} ({nationality_label(data['nationality'])})"
        if arrays is not None:
            attributes["percentage"] = arrays.records[SOLDIER_ARRAY_PERCENTAGE].values["values"][slot]
        if alternate is not None:
            attributes["alternate_cell"] = alternate

        result.append(
            PlacedEntity(
                category=EntityCategory.SOLDIER,
                x=cell[0],
                y=cell[1],
                z=cell[2],
                source=TABLE_SOLDIER_POSITIONS,
                slot_index=slot,
                label=label,
                sprite_archive=ARCHIVE_PEOPLE,
                sprite_frame=record.values["frame"],
                attributes=attributes,
                anomalies=_flag_check(map_doc, cell, FLAG_SOLDIER),
            )
        )
        if alternate is not None:
            # The Scenario Builder shows a dice token where a soldier may be relocated to
            result.append(
                PlacedEntity(
                    category=EntityCategory.RELOCATION,
                    x=alternate[0],
                    y=alternate[1],
                    z=alternate[2],
                    source=TABLE_SOLDIER_POSITIONS,
                    slot_index=slot,
                    label=f"alternate position of soldier {slot}",
                    sprite_archive=ARCHIVE_TOKEN,
                    sprite_frame=TOKEN_FRAME_RELOCATION,
                    attributes={"soldier": slot, "soldier_cell": cell},
                    anomalies=_flag_check(map_doc, alternate, FLAG_SOLDIER),
                )
            )
    return result


def _turret_parts(post_tile: PostTileData) -> List[PlacedEntity]:
    table = post_tile.get_table(TABLE_TURRET_GROUPS)
    if table is None:
        return []
    result: List[PlacedEntity] = []
    for record in table.records:
        state = record.values["state"]
        for part in range(TURRET_PARTS_PER_GROUP):
            cell: Optional[Tuple[int, int, int]] = record.values[f"part_{part:02d}_cell"]
            frame = record.values[f"part_{part:02d}_frame"]
            # Unused part slots are zero-filled: cell index 0 with frame 0
            if cell is None or (cell == (0, 0, 0) and frame == 0):
                continue
            result.append(
                PlacedEntity(
                    category=EntityCategory.TURRET,
                    x=cell[0],
                    y=cell[1],
                    z=cell[2],
                    source=TABLE_TURRET_GROUPS,
                    slot_index=record.slot_index,
                    label=f"turret group {record.slot_index} part {part}",
                    sprite_archive=ARCHIVE_TURRET,
                    sprite_frame=frame,
                    attributes={
                        "group": record.slot_index,
                        "part": part,
                        "state": state,
                        # The engine only draws groups whose state word is 0
                        "hidden": state != 0,
                    },
                )
            )
    return result


def _items(post_tile: PostTileData, map_doc: MapDocument) -> List[PlacedEntity]:
    """Items lying in canisters (holder type 0); items carried by soldiers are not placed on the map."""
    table = post_tile.get_table(TABLE_ITEMS)
    if table is None:
        return []
    result: List[PlacedEntity] = []
    for record in table.used_records:
        if record.values["holder_type"] != ITEM_HOLDER_CANISTER:
            continue
        cell = decode_cell_index(record.values["holder"])
        if cell is None:
            continue
        item_class, item_kind = record.values["item_class"], record.values["item_kind"]
        result.append(
            PlacedEntity(
                category=EntityCategory.ITEM,
                x=cell[0],
                y=cell[1],
                z=cell[2],
                source=TABLE_ITEMS,
                slot_index=record.slot_index,
                label=f"item in canister (class {item_class}, kind {item_kind})",
                attributes={"item_class": item_class, "item_kind": item_kind},
                anomalies=_flag_check(map_doc, cell, FLAG_CANISTER),
            )
        )
    return result


def _cell_flag_entities(cells: Iterable[MapCell]) -> List[PlacedEntity]:
    """Entities the engine draws directly from cell flags (sub_43505D)."""
    result: List[PlacedEntity] = []
    for cell in cells:
        flags = cell.flags
        # Bits 16..22 hold the default 0x1F and the floor cover level; skip plain cells fast
        if not flags & 0xFF80FFFF:
            continue

        if flags & FLAG_CANISTER:
            frame = (flags >> 12) & 0x3F
            result.append(
                PlacedEntity(
                    category=EntityCategory.CANISTER,
                    x=cell.x,
                    y=cell.y,
                    z=cell.z,
                    source="cell flags",
                    label=f"item / canister (Can.obj frame {frame})",
                    sprite_archive=ARCHIVE_CAN,
                    sprite_frame=frame,
                )
            )

        for mask, frame, label in _SINGLE_BIT_MARKERS:
            if flags & mask:
                result.append(_marker(cell, frame, label))

        multiplayer = (flags >> 24) & 7
        if multiplayer:
            result.append(_marker(cell, multiplayer - 1, f"multiplayer marker {multiplayer}"))

        effect = (flags >> 28) & 7
        if effect:
            result.append(_marker(cell, effect + 12, f"area effect {effect}"))
    return result


def _marker(cell: MapCell, frame: int, label: str) -> PlacedEntity:
    return PlacedEntity(
        category=EntityCategory.MARKER,
        x=cell.x,
        y=cell.y,
        z=cell.z,
        source="cell flags",
        label=label,
        sprite_archive=ARCHIVE_TOKEN,
        sprite_frame=frame,
    )
