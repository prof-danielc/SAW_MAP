"""Plain-text report of the post-tile record tables and placed entities of a map.

Lists every decoded table with its position, slot usage, field layout with evidence
status, and per-record field values, followed by the placed entities and anomalies.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, List

from saw_map.maps.model import MapDocument
from saw_map.maps.records import CELL_MARK_CATEGORIES, EntityCategory, FieldKind, FieldSpec, Record, RecordTable

# Long word arrays are abbreviated to this many leading values
_ARRAY_PREVIEW = 12


def _format_value(spec: FieldSpec, value: Any) -> str:
    """Formats one decoded field value for the report."""
    if spec.kind == FieldKind.BYTES:
        return value.hex()
    if spec.kind == FieldKind.CELL_REF:
        return "None" if value is None else f"({value[0]}, {value[1]}, {value[2]})"
    if spec.kind == FieldKind.U16_ARRAY:
        shown = " ".join(str(v) for v in value[:_ARRAY_PREVIEW])
        return f"[{shown}{' ...' if len(value) > _ARRAY_PREVIEW else ''}]"
    return str(value)


def _format_record(table: RecordTable, record: Record) -> str:
    parts = [f"{spec.name}={_format_value(spec, record.values[spec.name])}" for spec in table.layout.fields]
    marker = "" if record.in_use else " (unused)"
    return f"  slot {record.slot_index:3d}{marker}: " + " ".join(parts)


def _format_table(table: RecordTable, include_unused: bool) -> List[str]:
    layout = table.layout
    used = table.used_records
    lines = [
        f"[{layout.table_id}] {layout.working_name} ({layout.status.value}) | offset {table.offset} | "
        f"{layout.slot_count} slots x {layout.record_size} bytes | {len(used)} in use",
    ]
    if layout.description:
        lines.append(f"  {layout.description}")
    lines.append(f"  source: {layout.source_reference}")
    lines.append(
        "  fields: " + " ".join(f"{spec.name}:{spec.kind.value}({spec.status.value})" for spec in layout.fields)
    )
    for record in table.records if include_unused else used:
        lines.append(_format_record(table, record))
    return lines


def format_records_report(map_doc: MapDocument, include_unused: bool = False) -> str:
    """Formats the post-tile tables and placed entities of a map as plain text.

    Args:
        map_doc: Loaded map document.
        include_unused: If True, unused record slots are listed as well.

    Returns:
        Multi-line report. When the post-tile data was not decoded, the report states why.
    """
    name = map_doc.name or map_doc.title
    lines = [f"POST-TILE DATA: {name} (version {map_doc.version})"]

    post_tile = map_doc.post_tile
    if post_tile is None:
        lines.append("Status: no post-tile data loaded")
        return "\n".join(lines) + "\n"
    if not post_tile.is_decoded:
        lines.append(
            f"Status: {post_tile.status.value} | offset {post_tile.start_offset} | "
            f"{post_tile.byte_size} bytes | {post_tile.status_detail}"
        )
        return "\n".join(lines) + "\n"

    assigned = sum(table.layout.byte_size for table in post_tile.tables)
    lines.append(
        f"Status: {post_tile.status.value} | offset {post_tile.start_offset} | {post_tile.byte_size} bytes | "
        f"{len(post_tile.tables)} tables | {post_tile.byte_size - assigned} bytes unassigned"
    )

    for table in post_tile.tables:
        lines.append("")
        lines.extend(_format_table(table, include_unused))

    placed = [e for e in map_doc.entities if e.category not in CELL_MARK_CATEGORIES]
    markers = Counter(e.label for e in map_doc.entities if e.category == EntityCategory.MARKER)
    lines.extend(["", f"PLACED ENTITIES: {len(placed)}"])
    for entity in placed:
        sprite = "-" if entity.sprite_archive is None else f"{entity.sprite_archive}.obj:{entity.sprite_frame}"
        source = entity.source if entity.slot_index < 0 else f"{entity.source}[{entity.slot_index}]"
        attributes = " ".join(f"{k}={v}" for k, v in entity.attributes.items())
        anomalies = f"  ! {', '.join(entity.anomalies)}" if entity.anomalies else ""
        lines.append(
            f"  {entity.category.value:<13} ({entity.x}, {entity.y}, {entity.z})  {sprite:<16} {source:<14} "
            f"{attributes}{anomalies}".rstrip()
        )

    lines.append(f"EDITOR MARKERS (cell flags): {sum(markers.values())}")
    for label, count in sorted(markers.items()):
        lines.append(f"  {label}: {count} cells")

    effects = Counter(e.label for e in map_doc.entities if e.category == EntityCategory.EFFECT)
    lines.append(f"AREA EFFECTS (cell flags): {sum(effects.values())}")
    for label, count in sorted(effects.items()):
        lines.append(f"  {label}: {count} cells")

    lines.append(f"ANOMALIES: {sum(1 for e in map_doc.entities if e.anomalies)}")
    return "\n".join(lines) + "\n"
