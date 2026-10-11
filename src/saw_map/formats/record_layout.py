"""Declarative layouts of the post-tile record tables of Soldiers at War map streams.

The version 21 layout is a transcription, in stream order, of the read calls of the
engine's map loader (SAW_TD sub_445F25, SAW_TD_NOTES.c lines 41838-41983). It totals
31,366 bytes and consumes every shipped version 21 map exactly.

Field names are generic (field_NN, or field_mNNN when named after the in-memory offset
of a soldier record) until their meaning is established. Every field carries an
evidence status; see REVERSE_ENGINEERING_INFO.md section 9 for the evidence.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from saw_map.maps.records import EvidenceStatus, FieldKind, FieldSpec, TableLayout

_CONFIRMED = EvidenceStatus.CONFIRMED
_HYPOTHESIS = EvidenceStatus.HYPOTHESIS
_UNKNOWN = EvidenceStatus.UNKNOWN

# Table identifiers referenced by entity extraction
TABLE_INFO_ITEMS = "T-554A80"
TABLE_TOKENS = "T-559230"
TABLE_SOLDIER_POSITIONS = "T-554F60"
TABLE_TURRET_GROUPS = "T-550538"
TABLE_WINDOW = "S-543F18"
TABLE_SOLDIERS = "T-847E50"
TABLE_SOLDIER_ARRAYS = "S-847E50B"
TABLE_REINFORCEMENTS = "T-883800"
TABLE_ITEMS = "T-892AD0"

TURRET_PARTS_PER_GROUP = 20

# Slot of the soldier arrays table holding the appearance percentage of each soldier
SOLDIER_ARRAY_PERCENTAGE = 0


def _u16(name: str, status: EvidenceStatus = _UNKNOWN, note: str = "") -> FieldSpec:
    return FieldSpec(name, FieldKind.U16, 2, status, note)


def _u32(name: str, status: EvidenceStatus = _UNKNOWN, note: str = "") -> FieldSpec:
    return FieldSpec(name, FieldKind.U32, 4, status, note)


def _i32(name: str, status: EvidenceStatus = _UNKNOWN, note: str = "") -> FieldSpec:
    return FieldSpec(name, FieldKind.I32, 4, status, note)


def _cell(name: str, status: EvidenceStatus = _UNKNOWN, note: str = "") -> FieldSpec:
    return FieldSpec(name, FieldKind.CELL_REF, 4, status, note)


def _raw(name: str, size: int) -> FieldSpec:
    return FieldSpec(name, FieldKind.BYTES, size)


def _u16_array(name: str, count: int, status: EvidenceStatus = _UNKNOWN, note: str = "") -> FieldSpec:
    return FieldSpec(name, FieldKind.U16_ARRAY, 2 * count, status, note)


def _generic_u16(count: int, start: int = 0) -> List[FieldSpec]:
    return [_u16(f"field_{start + i:02d}") for i in range(count)]


def _turret_part_fields() -> List[FieldSpec]:
    fields: List[FieldSpec] = []
    for i in range(TURRET_PARTS_PER_GROUP):
        fields.append(
            _cell(
                f"part_{i:02d}_cell",
                _CONFIRMED,
                "sub_4352FD compares dword_55056C[85*g + 3*i] with the drawn cell index",
            )
        )
        fields.append(
            _u16(
                f"part_{i:02d}_frame",
                _CONFIRMED,
                "sub_4352FD draws Turret.obj frame word_550570[170*g + 6*i]; valid frame in all maps",
            )
        )
    return fields


def _build_v21_layout() -> Tuple[TableLayout, ...]:
    return (
        TableLayout(
            table_id=TABLE_INFO_ITEMS,
            working_name="information_tokens",
            slot_count=40,
            fields=(
                _u32(
                    "target",
                    _CONFIRMED,
                    "what the token is assigned to, by target_type: the token's own cell index (348 of 348 "
                    "slots), a soldier slot in use (192 of 192), or an item slot in use (10 of 10)",
                ),
                _u16(
                    "target_type",
                    _CONFIRMED,
                    "0 Cell, 5 Character, 9 Item (the dialog's 'Assign Token'); 9 for Airfield token 3, assigned "
                    "to item 'Map'; 5 pairs with Target Eliminate in 142 slots",
                ),
                _u16("radius", _HYPOTHESIS, "0 for Airfield token 3, as in its dialog ('Token Radius'); 0..32"),
                _u16("field_08"),
                _u16(
                    "condition",
                    _CONFIRMED,
                    "index into None, Target Get, Target Eliminate, Target Destination, Trigger: 1 for Airfield "
                    "token 3 (Target Get); values 0..4 in all maps",
                ),
                _u16(
                    "causes",
                    _CONFIRMED,
                    "index into None, Immediate Victory, Immediate Defeat, One Goal Met: 3 for Airfield token 3 "
                    "(One Goal Met); values 0, 2, 3 in all maps",
                ),
                _cell(
                    "cell",
                    _CONFIRMED,
                    "cells of used slots are exactly the cells with flag bit 7 in all 95 maps",
                ),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41841-41847 (dword_554A80)",
            used_cell_field="cell",
            unused_when_all_ff=True,
            description=(
                "Information tokens (mission triggers and objectives) placed with the Scenario Builder's "
                "'Info' mode, which writes dword_554A80 and sets cell flag bit 7. The slot index is the "
                "Token ID; the popup text is line (ID + 1) of the companion .txt file. Drawn as the folder "
                "icon, Token.obj frame 5."
            ),
        ),
        TableLayout(
            table_id=TABLE_TOKENS,
            working_name="tokens",
            slot_count=40,
            fields=(
                _cell(
                    "cell",
                    _CONFIRMED,
                    "sub_447F93 looks the cell up; cells equal those with flag bit 10 in all 95 maps",
                ),
                _u16("frame", _CONFIRMED, "sub_434FB0 draws Token.obj frame word_559234[4*i]"),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41851-41852 (dword_559230)",
            used_cell_field="cell",
            description=(
                "Reinforcement tokens. The editor modes A / G / N Reinforce write Token.obj frame 7 (star), "
                "8 (cross), 9 (flag)."
            ),
        ),
        TableLayout(
            table_id=TABLE_SOLDIER_POSITIONS,
            working_name="soldier_positions",
            slot_count=40,
            fields=(
                _cell(
                    "cell",
                    _CONFIRMED,
                    "sub_435562 matches dword_554F68[4*i] with the drawn cell; Airfield slot 17 at (44,41,0)",
                ),
                _u16("hidden", _CONFIRMED, "sub_435562 draws the soldier only when word_554F66[8*i] is 0"),
                _u16("field_12"),
                _cell(
                    "alternate_cell",
                    _CONFIRMED,
                    "written by the editor's character relocation mode; the dice tokens of airfield_dices_1..3.png "
                    "sit on the alternate cells of slots 16, 22, 23, and every such cell carries flag bit 5",
                ),
                _u16("frame", _CONFIRMED, "sub_435562 draws People.obj frame word_554F64[8*i]"),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41856-41860 (dword_554F60)",
            used_cell_field="cell",
            description=(
                "Position, optional alternate position, and People.obj frame of each soldier (the editor's "
                "Character ID is the slot index); parallel to the soldiers table."
            ),
        ),
        TableLayout(
            table_id=TABLE_TURRET_GROUPS,
            working_name="turret_groups",
            slot_count=10,
            fields=tuple(
                [
                    _u16(
                        "state",
                        _CONFIRMED,
                        "sub_4352FD only draws groups whose first word is 0; the Airfield group (state 1) "
                        "is absent from the Scenario Builder screenshot",
                    )
                ]
                + _generic_u16(5, start=1)
                + [_raw("field_06", 40)]
                + _generic_u16(4, start=7)
                + _turret_part_fields()
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41864-41878 (word_550538)",
            description="Multi-cell objects drawn from Turret.obj; shipped maps use 9 parts (3 x 3 cells) per group.",
        ),
        TableLayout(
            table_id=TABLE_WINDOW,
            working_name="playable_window",
            slot_count=1,
            fields=(
                _i32("max_x", _CONFIRMED, "equals min_x + width of the companion .txt in all 95 maps"),
                _i32("max_y", _CONFIRMED, "equals min_y + height of the companion .txt in all 95 maps"),
                _i32("min_x", _CONFIRMED, "equals (130 - width) // 2 in all 95 maps"),
                _i32("min_y", _CONFIRMED, "equals (100 - height) // 2 in all 95 maps"),
                _u16("field_16"),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41881-41885 (dword_543F18, 543F14, 543F1C, 543F20)",
            description="Exclusive maximum and inclusive minimum column/row of the playable area.",
        ),
        TableLayout(
            table_id="T-558FE8",
            working_name="table_558FE8",
            slot_count=8,
            fields=(_raw("data", 8),),
            source_reference="sub_445F25 line 41887 (unk_558FE8)",
        ),
        TableLayout(
            table_id="T-550328",
            working_name="table_550328",
            slot_count=8,
            fields=(_raw("data", 8),),
            source_reference="sub_445F25 line 41889 (dword_550328)",
        ),
        TableLayout(
            table_id="S-884828",
            working_name="editor_selection",
            slot_count=1,
            fields=(
                _u16("cell_x", _HYPOTHESIS, "57 -> 37 after editing the character at (37,24) and saving"),
                _u16("cell_y", _HYPOTHESIS, "49 -> 24 after editing the character at (37,24) and saving"),
                _u16("field_02"),
            ),
            status=_HYPOTHESIS,
            description="Column and row of the cell last selected in the Scenario Builder.",
            source_reference="sub_445F25 lines 41890-41892 (word_884828)",
        ),
        TableLayout(
            table_id=TABLE_SOLDIERS,
            working_name="soldiers",
            slot_count=40,
            fields=(
                _u16(
                    "nationality",
                    _CONFIRMED,
                    "2 for Character ID 23, shown as German in airfield_dices_3_character.png; 4 for two civilians "
                    "added with the editor; same codes (1, 2, 4) as the reinforcement table, which pair with the "
                    "A/G/N Reinforce token frames",
                ),
                _u16(
                    "rank",
                    _CONFIRMED,
                    "index into the editor's rank list (0 Private .. 18 Col General): 13, 7, 6, 8 for the "
                    "Lt Colonel, Sgt Major, Senior Sgt, Staff Sgt of Airfield IDs 9, 10, 23, 39",
                ),
                _u16(
                    "controller",
                    _CONFIRMED,
                    "0 Computer, 1 Human: 0 for ID 23 (Computer), 1 for the 8 player soldiers of Airfield",
                ),
                _u16(
                    "ai",
                    _CONFIRMED,
                    "index into the editor's alphabetical AI list (0 Follower .. 7 Wander): 1 for ID 23 (Guard); "
                    "5 is Seeker in the reinforcement dialog; values 0..7 in all maps",
                ),
                _u32(
                    "field_medic",
                    _CONFIRMED,
                    "0 -> 1 is the only soldier-record change between Airfield.map and a copy saved after "
                    "ticking 'Field Medic' for Character ID 9",
                ),
                _u16("field_m306"),
                _u16(
                    "primary_training",
                    _CONFIRMED,
                    "index into the editor's training list (0 None .. 6 Explosive): 1, 2, 3, 4 for the Pistol, "
                    "Submachinegun, Bolt Action, Semi/Automatic of Airfield IDs 9, 10, 23, 39",
                ),
                _u16(
                    "secondary_training",
                    _CONFIRMED,
                    "same list: 2, 4, 2, 1 for the Submachinegun, Semi/Automatic, Submachinegun, Pistol of "
                    "Airfield IDs 9, 10, 23, 39",
                ),
                _u16("encumbrance", _HYPOTHESIS, "30 for ID 23, as in its Character Stats dialog; range 17..32"),
                _u16(
                    "facing",
                    _CONFIRMED,
                    "0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW on screen (IDs 9, 10, 39 of Airfield face S, SE, "
                    "SW with values 4, 3, 5); People.obj frame = 8 * appearance + (facing + 4) % 8 holds for "
                    "1,831 of 1,852 soldiers",
                ),
                _u32("field_m000"),
                _u32("field_m004"),
                _u32("field_m008"),
                _u32(
                    "appearance",
                    _CONFIRMED,
                    "0..20, the 21 body types of People.obj (168 frames = 21 x 8 facings); see 'facing'. "
                    "15 and 16 are the male and female civilians added in a controlled edit",
                ),
                _u16(
                    "field_m308",
                    _HYPOTHESIS,
                    "0..89 in original soldiers, 0xFFFF in characters newly created with the editor; possibly the "
                    "index of a predefined character (name / portrait)",
                ),
                _u16_array(
                    "loadout",
                    192,
                    _CONFIRMED,
                    "inventory grid of 8 areas x 4 rows x 6 columns; each word is an item slot (all 27,813 non-empty "
                    "words in 95 maps index an in-use slot) and a large item repeats over the cells it covers",
                ),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41895-41915 (unk_847E50, 1,760-byte memory records)",
            description="Per-soldier data; slot n belongs to slot n of the soldier positions table.",
        ),
        TableLayout(
            table_id="S-847E50B",
            working_name="soldier_arrays",
            slot_count=2,
            fields=(_u16_array("values", 40, _HYPOTHESIS, "one word per soldier slot"),),
            status=_HYPOTHESIS,
            source_reference="sub_445F25 lines 41920-41921 (unk_847E50 + 70400)",
            description=(
                "Two arrays of one word per soldier. Slot 0: appearance percentage (100 for Character ID 23, "
                "as in its Character Stats dialog; values 5..100). Slot 1: a 0/1 flag, 1 for most human-controlled "
                "soldiers; it dropped to 0 when two of them were replaced by civilians."
            ),
        ),
        TableLayout(
            table_id=TABLE_REINFORCEMENTS,
            working_name="reinforcements",
            slot_count=40,
            fields=(
                _u16(
                    "nationality",
                    _CONFIRMED,
                    "1 / 2 / 4 pair exactly with token frames 7 / 8 / 9 (A / G / N Reinforce) in all 95 maps",
                ),
                _u16(
                    "character_type",
                    _CONFIRMED,
                    "index into the dialog's list, for German tokens Infantry, Grenadier, Officer, SS Infantry, "
                    "SS Officer: 3 for the token at (75,88,0) (SS Infantry); German tokens use 0..4",
                ),
                _u16(
                    "percentage",
                    _CONFIRMED,
                    "50 for the token at (75,88,0), as in airfield_reinforcement_token_2.png",
                ),
                _u16("controller", _CONFIRMED, "0 Computer, 1 Human; 0 for the token at (75,88,0) and every used slot"),
                _u16(
                    "ai",
                    _CONFIRMED,
                    "index into the soldier AI list; the dialog offers Seeker and Wander and the data holds only "
                    "5 and 7; 5 for the token at (75,88,0) (Seeker)",
                ),
                _u16(
                    "turn_or_token",
                    _CONFIRMED,
                    "the dialog's 'Turn/Token': 0 for the token at (75,88,0); non-zero only with entry conditions "
                    "Trigger, Turn Limit (turn number), and Condition (token id)",
                ),
                _u16(
                    "entry_condition",
                    _CONFIRMED,
                    "index into Target Eliminate, Target Get, Target Destination, Sighted, Trigger, Turn Limit, "
                    "Condition: 0 for the token at (75,88,0) (Target Eliminate); values 0, 1, 4, 5, 6 in all maps",
                ),
                _u16("amount", _CONFIRMED, "1 for the token at (75,88,0), as in its dialog; range 1..6"),
                _u16("field_08"),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41924-41932 (word_883800)",
            description="Reinforcement settings of each token; slot n belongs to slot n of the tokens table.",
        ),
        TableLayout(
            table_id="S-884750A",
            working_name="mission_params_a",
            slot_count=1,
            fields=(
                _u16("field_00"),
                _u16("field_01"),
                _u16("field_04"),
                _u32("field_06"),
                _u32("field_08"),
                _u16("field_10"),
            ),
            source_reference="sub_445F25 lines 41934-41939 (word_884750)",
        ),
        TableLayout(
            table_id="T-884750B",
            working_name="mission_params_b",
            slot_count=8,
            fields=(_u32("field_00"), _u16("field_02"), _u16("field_03")),
            source_reference="sub_445F25 lines 41942-41944 (word_884750 + 12)",
        ),
        TableLayout(
            table_id="S-884750C",
            working_name="mission_params_c",
            slot_count=1,
            fields=tuple(_generic_u16(4, start=44) + [_raw("field_48", 8)]),
            source_reference="sub_445F25 lines 41946-41950 (word_884750 + 44)",
        ),
        TableLayout(
            table_id="T-884750D",
            working_name="mission_params_d",
            slot_count=8,
            fields=(_raw("field_a", 6), _raw("field_b", 6)),
            source_reference="sub_445F25 lines 41953-41954 (word_884750 + 53)",
        ),
        TableLayout(
            table_id="S-884750E",
            working_name="mission_params_e",
            slot_count=1,
            fields=tuple(_generic_u16(3, start=101)),
            source_reference="sub_445F25 lines 41956-41958 (word_884750 + 101)",
        ),
        TableLayout(
            table_id="T-8923C0",
            working_name="table_8923C0",
            slot_count=100,
            fields=tuple(_generic_u16(3)),
            source_reference="sub_445F25 lines 41961-41963 (word_8923C0)",
        ),
        TableLayout(
            table_id=TABLE_ITEMS,
            working_name="items",
            slot_count=500,
            fields=(
                _u16(
                    "holder_type",
                    _CONFIRMED,
                    "5 = carried by a soldier, 0 = lying in a canister; see 'holder'",
                ),
                _u32(
                    "holder",
                    _CONFIRMED,
                    "soldier slot when holder_type is 5 (10,529 of 10,546 such items are in exactly that soldier's "
                    "loadout; removing soldiers 6 and 7 in the editor freed exactly their items) or the canister's "
                    "cell index when holder_type is 0 (all 4,072 such cells carry the canister flag)",
                ),
                _u16("field_04"),
                _u16("item_class", _HYPOTHESIS, "1..5; the loader special-cases class 1 (line 41974)"),
                _u16("item_kind", _HYPOTHESIS, "index within the class; class 5 kind 7 is the 'Map' of Airfield"),
                _u16("field_07"),
                _u32("field_12"),
            ),
            status=_CONFIRMED,
            source_reference="sub_445F25 lines 41967-41973 (word_892AD0)",
            unused_when_all_ff=True,
            description=(
                "Mission item pool. Every item is either carried by a soldier (and referenced from that "
                "soldier's loadout grid) or lies in the canister on a cell."
            ),
        ),
        TableLayout(
            table_id="T-559530",
            working_name="table_559530",
            slot_count=8,
            fields=(_raw("field_a", 8), _raw("field_b", 8), _raw("field_c", 8), _raw("field_d", 8)),
            source_reference="sub_445F25 lines 41979-41982 (dword_559530, 559570, 5595B0, 5595F0)",
        ),
    )


_LAYOUTS: Dict[str, Tuple[TableLayout, ...]] = {
    "21": _build_v21_layout(),
}


def get_layout(version: str) -> Optional[Sequence[TableLayout]]:
    """Returns the ordered table layouts for a stream version, or None if no layout is known."""
    return _LAYOUTS.get(version)


def layout_byte_size(layout: Sequence[TableLayout]) -> int:
    """Total bytes consumed by a layout (sum of slot_count * record_size)."""
    return sum(table.byte_size for table in layout)
