"""Row-based RLE sprite reader and archive decoder for Soldiers at War graphical assets (.obj, .spr).

Decodes sprite archives into indexed pixel buffers, alpha transparency masks,
and converts to true-color RGBA Pillow images.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image

from saw_map.formats.palette_reader import Palette

ARCHIVE_HEADER_SIZE = 32
INDEX_ENTRY_SIZE = 8
SPRITE_HEADER_SIZE = 24


@dataclass(slots=True)
class SpriteFrame:
    """Represents a single decoded sprite frame within an archive."""
    frame_index: int
    width: int
    height: int
    offset_x: int
    offset_y: int
    unk0: int
    unk1: int
    raw_indexed_data: bytes
    alpha_mask: bytes

    def to_rgba(self, palette: Palette) -> Image.Image:
        """Converts indexed pixel data and alpha mask into a true-color RGBA PIL image."""
        total_pixels = self.width * self.height
        if total_pixels == 0:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        rgba_bytes = bytearray(total_pixels * 4)
        data = self.raw_indexed_data
        alpha = self.alpha_mask

        # Fast direct byte array packing
        for i in range(total_pixels):
            a = alpha[i]
            if a:
                r, g, b = palette.get_color(data[i])
                base_idx = i * 4
                rgba_bytes[base_idx] = r
                rgba_bytes[base_idx + 1] = g
                rgba_bytes[base_idx + 2] = b
                rgba_bytes[base_idx + 3] = a

        return Image.frombytes("RGBA", (self.width, self.height), bytes(rgba_bytes))


@dataclass
class SpriteArchive:
    """Represents an archive (.obj/.spr) containing indexed sprite frames."""
    name: str
    sprite_count: int
    frames: List[SpriteFrame] = field(default_factory=list)

    def get_frame(self, index: int) -> Optional[SpriteFrame]:
        """Retrieves a sprite frame by its index, or None if out of bounds."""
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None


class SpriteReader:
    """Decodes Soldiers at War sprite archive formats and scanline RLE streams."""

    @staticmethod
    def decode_rle(encoded_data: bytes, width: int, height: int) -> Tuple[bytes, bytes]:
        """Decodes scanline-based RLE encoded sprite payload.

        RLE Commands per row:
            0x00: End of row
            0x80: Transparent pixel run (next byte = length)
            cmd & 0x80: Literal pixel copy (length = cmd & 0x7F, copy length bytes)
            cmd < 0x80: Repeated pixel byte (length = cmd, repeat next byte length times)
        """
        total_pixels = width * height
        if total_pixels == 0:
            return (b"", b"")

        data = bytearray(total_pixels)
        alpha = bytearray(total_pixels)

        read_ptr = 0
        write_ptr = 0
        encoded_len = len(encoded_data)

        for _ in range(height):
            while read_ptr < encoded_len:
                cmd = encoded_data[read_ptr]
                read_ptr += 1

                if cmd == 0x00:
                    # End of scanline
                    break

                if cmd == 0x80:
                    # Transparent pixel run
                    if read_ptr < encoded_len:
                        length = encoded_data[read_ptr]
                        read_ptr += 1
                        write_ptr += length
                elif cmd & 0x80:
                    # Literal copy
                    length = cmd & 0x7F
                    end_read = min(read_ptr + length, encoded_len)
                    actual_len = end_read - read_ptr
                    if actual_len > 0 and write_ptr + actual_len <= total_pixels:
                        data[write_ptr : write_ptr + actual_len] = encoded_data[read_ptr:end_read]
                        alpha[write_ptr : write_ptr + actual_len] = b"\xFF" * actual_len
                    write_ptr += length
                    read_ptr += length
                else:
                    # Repeated byte
                    length = cmd
                    if read_ptr < encoded_len:
                        val = encoded_data[read_ptr]
                        read_ptr += 1
                        if write_ptr + length <= total_pixels:
                            data[write_ptr : write_ptr + length] = bytes([val]) * length
                            alpha[write_ptr : write_ptr + length] = b"\xFF" * length
                        write_ptr += length

        return (bytes(data), bytes(alpha))

    @classmethod
    def read_archive(cls, file_path: Union[str, Path]) -> SpriteArchive:
        """Parses a sprite archive file (.obj / .spr) from disk."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Sprite archive not found: {path}")

        data = path.read_bytes()
        return cls.read_archive_bytes(data, name=path.name)

    @classmethod
    def read_archive_bytes(cls, data: bytes, name: str = "custom.obj") -> SpriteArchive:
        """Parses a sprite archive file from memory bytes."""
        if len(data) < ARCHIVE_HEADER_SIZE:
            raise ValueError(f"Archive buffer too small ({len(data)} bytes, minimum 32 bytes required)")

        # Unpack archive header
        sprite_count, idx_off, idx_size, arr_off, arr_size = struct.unpack("<IIIII", data[:20])

        if idx_off + idx_size > len(data):
            raise ValueError("Corrupted archive header: index table offset exceeds file size")

        # Read index table entries
        entries: List[Tuple[int, int]] = []
        for i in range(sprite_count):
            entry_offset = idx_off + (i * INDEX_ENTRY_SIZE)
            if entry_offset + INDEX_ENTRY_SIZE > len(data):
                break
            rel_off, byte_sz = struct.unpack("<II", data[entry_offset : entry_offset + 8])
            entries.append((rel_off, byte_sz))

        frames: List[SpriteFrame] = []
        for frame_idx, (rel_off, byte_sz) in enumerate(entries):
            sprite_abs_offset = arr_off + rel_off
            if sprite_abs_offset + SPRITE_HEADER_SIZE > len(data):
                continue

            # Read sprite header
            header_bytes = data[sprite_abs_offset : sprite_abs_offset + SPRITE_HEADER_SIZE]
            ox, oy, w, h, u0, u1, data_sz = struct.unpack("<HHHHHHI", header_bytes[:16])

            encoded_start = sprite_abs_offset + SPRITE_HEADER_SIZE
            encoded_end = encoded_start + data_sz
            encoded_payload = data[encoded_start:encoded_end]

            raw_data, alpha_mask = cls.decode_rle(encoded_payload, w, h)

            frame = SpriteFrame(
                frame_index=frame_idx,
                width=w,
                height=h,
                offset_x=ox,
                offset_y=oy,
                unk0=u0,
                unk1=u1,
                raw_indexed_data=raw_data,
                alpha_mask=alpha_mask,
            )
            frames.append(frame)

        return SpriteArchive(name=name, sprite_count=len(frames), frames=frames)
