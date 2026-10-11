"""Unit tests for row-based RLE sprite decoding, alpha masks, and archive structures."""

from pathlib import Path
import pytest
from saw_map.formats.palette_reader import Palette
from saw_map.formats.sprite_reader import SpriteArchive, SpriteFrame, SpriteReader


def make_dummy_palette() -> Palette:
    """Creates a simple 256-color gradient palette for testing."""
    colors = [(i, (i * 2) % 256, (i * 3) % 256) for i in range(256)]
    return Palette(name="dummy.pal", rgb_table=colors)


def test_rle_transparent_skip():
    """Validates 0x80 transparent skip command."""
    # 4x1 sprite: 2 transparent pixels (0x80 0x02), 2 literal pixels (0x82 0x0A 0x0B), end of row (0x00)
    encoded = bytes([0x80, 2, 0x82, 10, 11, 0x00])
    data, alpha = SpriteReader.decode_rle(encoded, width=4, height=1)

    assert len(data) == 4
    assert len(alpha) == 4
    # First 2 pixels transparent
    assert alpha[0] == 0
    assert alpha[1] == 0
    # Next 2 pixels opaque
    assert alpha[2] == 255
    assert alpha[3] == 255
    assert data[2] == 10
    assert data[3] == 11


def test_rle_repeat_run():
    """Validates cmd < 0x80 repeat run command."""
    # 4x1 sprite: repeat pixel value 42 four times (0x04 0x2A), end of row (0x00)
    encoded = bytes([4, 42, 0x00])
    data, alpha = SpriteReader.decode_rle(encoded, width=4, height=1)

    assert len(data) == 4
    assert data == bytes([42, 42, 42, 42])
    assert alpha == bytes([255, 255, 255, 255])


def test_rle_multi_row():
    """Validates multi-row sprite decoding."""
    # 2x2 sprite:
    # Row 0: 2 literal pixels (0x82, 1, 2, 0x00)
    # Row 1: 1 transparent, 1 literal (0x80, 1, 0x81, 3, 0x00)
    encoded = bytes([0x82, 1, 2, 0x00, 0x80, 1, 0x81, 3, 0x00])
    data, alpha = SpriteReader.decode_rle(encoded, width=2, height=2)

    assert len(data) == 4
    assert data[0] == 1 and data[1] == 2
    assert alpha[0] == 255 and alpha[1] == 255
    assert alpha[2] == 0 and alpha[3] == 255
    assert data[3] == 3


def test_sprite_to_rgba():
    """Validates conversion to PIL Image RGBA."""
    pal = make_dummy_palette()
    # 2x1 frame: pixel 0 transparent, pixel 1 color index 5
    data = bytes([0, 5])
    alpha = bytes([0, 255])
    frame = SpriteFrame(
        frame_index=0,
        width=2,
        height=1,
        offset_x=0,
        offset_y=0,
        unk0=0,
        unk1=0,
        raw_indexed_data=data,
        alpha_mask=alpha,
    )
    img = frame.to_rgba(pal)
    assert img.size == (2, 1)
    assert img.mode == "RGBA"

    p0 = img.getpixel((0, 0))
    p1 = img.getpixel((1, 0))
    assert p0[3] == 0  # transparent
    assert p1[3] == 255  # opaque
    assert (p1[0], p1[1], p1[2]) == pal.get_color(5)


def test_real_sprite_archive_if_available():
    """Tests loading real sgrass.obj if present."""
    path = Path("Research/SSI/Soldiers at War/Obj/sgrass.obj")
    if not path.is_file():
        pytest.skip("sgrass.obj not present")

    archive = SpriteReader.read_archive(path)
    assert archive.sprite_count > 0
    frame0 = archive.get_frame(0)
    assert frame0 is not None
    assert frame0.width > 0
    assert frame0.height > 0
    assert len(frame0.raw_indexed_data) == frame0.width * frame0.height
    assert len(frame0.alpha_mask) == frame0.width * frame0.height
