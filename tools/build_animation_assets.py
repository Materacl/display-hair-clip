"""Render cat/heart frames and pack shared animations for ESP32 and HTML.

Requires Pillow. Run from any directory: python tools/build_animation_assets.py
The exported PNG pixels and RGB565 runs are checked for an exact match.
"""
from base64 import b64encode
from io import BytesIO
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FRAME_COUNT = 32


def load_cat_frames():
    """Adapt the linked Tenor GIF to a white pixel cat on a black background."""
    frames, durations = [], []
    with Image.open(ROOT / "assets/cat-source.gif") as source:
        for index in range(source.n_frames):
            source.seek(index)
            durations.append(source.info.get("duration", 70))
            # Recover the approximately 4x source pixel grid before scaling it.
            original = source.convert("RGB").resize((50, 45), Image.Resampling.NEAREST)
            frame = Image.new("RGB", original.size, "black")
            for y in range(original.height):
                for x in range(original.width):
                    red, green, blue = original.getpixel((x, y))
                    level = max(red, green, blue)
                    if level > 220:
                        color = (0, 0, 0)       # Original white background.
                    elif level > 100:
                        color = (248, 252, 255) # White fur.
                    elif level > 40:
                        color = (174, 186, 198) # Fur shading.
                    elif level > 8:
                        color = (72, 79, 91)    # Outline against black.
                    else:
                        color = (16, 20, 27)    # Eyes and facial details.
                    frame.putpixel((x, y), color)
            frames.append(frame)
    # One common crop preserves the original jump positions across all frames.
    bounds = [frame.getbbox() for frame in frames]
    crop = (min(box[0] for box in bounds), min(box[1] for box in bounds),
            max(box[2] for box in bounds), max(box[3] for box in bounds))
    scale = min(280 // (crop[2]-crop[0]), 154 // (crop[3]-crop[1]))
    size = ((crop[2]-crop[0])*scale, (crop[3]-crop[1])*scale)
    frames = [frame.crop(crop).resize(size, Image.Resampling.NEAREST) for frame in frames]
    if len(set(durations)) != 1:
        raise ValueError("Cat GIF must use equal frame durations for the shared player")
    return frames, sum(durations)


def pixel_heart(colors=("#b51042", "#ff326c", "#df164f", "#ffb6ce"), size=(16, 15)):
    """Mirror the silhouette before coloring, so every size stays symmetric."""
    outline, fill, shade, highlight = colors
    rows = ["..####....####..", ".######..######."] + ["################"]*6
    rows += [".##############.", "..############..", "...##########...",
             "....########....", ".....######.....", "......####......", ".......##......."]
    mask = Image.new("L", (16, 15))
    mask.putdata([255 if cell == "#" else 0 for row in rows for cell in row])
    mask = mask.resize(size, Image.Resampling.NEAREST)
    width, height = size
    mask.paste(ImageOps.mirror(mask.crop((0, 0, width//2, height))), (width//2, 0))
    pixel = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(pixel)
    for y in range(height):
        for x in range(width):
            if not mask.getpixel((x, y)):
                continue
            edge = any(not (0 <= nx < width and 0 <= ny < height) or not mask.getpixel((nx, ny))
                       for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)))
            shadow = (x+0.5)*16/width + (y+0.5)*15/height > 18
            draw.point((x, y), fill=outline if edge else (shade if shadow else fill))
    # Place the old stepped glint after resizing the symmetric silhouette.
    draw.line((round(3*width/16), round(2*height/15),
               round(5*width/16), round(2*height/15)), fill=highlight)
    draw.line((round(2*width/16), round(3*height/15),
               round(2*width/16), round(4*height/15)), fill=highlight)
    return pixel


def floating_heart_frame(phase):
    # Integer scaling preserves the symmetric pixel outline and shading.
    style = int(phase*FRAME_COUNT) % FRAME_COUNT
    colors = [("#b51042", "#ff326c", "#df164f", "#ffb6ce"),
              ("#9b1437", "#ff465e", "#d62045", "#ffc3ce"),
              ("#b93f79", "#ff87ba", "#df5296", "#ffe0ef"),
              ("#82256c", "#e45dbb", "#b53492", "#ffbde9")]
    scale = 1 if style % 8 < 4 else 2
    heart = pixel_heart(colors[style//8]).resize((16*scale, 15*scale), Image.Resampling.NEAREST)
    image = Image.new("RGB", (44, 44), "black")
    image.paste(heart, ((44-heart.width)//2, (44-heart.height)//2))
    return image


def rgb565(pixel):
    r, g, b = pixel
    return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3)


def expand565(value):
    return (round(((value >> 11) & 31)*255/31),
            round(((value >> 5) & 63)*255/63), round((value & 31)*255/31))


def pack(name, frames, period=None):
    width, height = frames[0].size
    frame_count = len(frames)
    atlas = Image.new("RGB", (width*8, height*((frame_count+7)//8)))
    for index, frame in enumerate(frames):
        atlas.paste(frame, ((index % 8)*width, (index//8)*height))
    reduced = atlas.quantize(colors=96, dither=Image.Dither.NONE).convert("RGB")
    raw = reduced.tobytes()
    values = [rgb565(raw[i:i+3]) for i in range(0, len(raw), 3)]
    palette = sorted(set(values) | {0})
    lookup = {value: index for index, value in enumerate(palette)}
    data, offsets = [], [0]
    indexed = Image.new("P", atlas.size)
    png_palette = [channel for value in palette for channel in expand565(value)]
    indexed.putpalette(png_palette + [0]*(768-len(png_palette)))
    indexed.putdata([lookup[value] for value in values])
    for index in range(frame_count):
        pixels = []
        for y in range(height):
            start = ((index//8)*height+y)*atlas.width+(index % 8)*width
            row = values[start:start+width]
            x = 0
            while x < width:
                end = x+1
                while end < width and row[end] == row[x] and end-x < 255:
                    end += 1
                data.extend((end-x, lookup[row[x]]))
                pixels.extend([row[x]]*(end-x))
                x = end
        # Decode the exported format, independent of the run writer.
        decoded = []
        for cursor in range(offsets[-1], len(data), 2):
            decoded.extend([palette[data[cursor+1]]]*data[cursor])
        assert decoded == pixels and len(decoded) == width*height
        offsets.append(len(data))
    output = BytesIO()
    # Transparent black matches the ESP32 decoder, which skips zero-color runs.
    indexed.save(output, format="PNG", optimize=True, transparency=lookup[0])
    png = output.getvalue()
    asset_dir = ROOT / "assets"
    asset_dir.mkdir(exist_ok=True)
    (asset_dir / f"{name}.png").write_bytes(png)
    def array(c_type, label, items, digits):
        lines = [f"static const {c_type} {label}[] PROGMEM = {{"]
        for offset in range(0, len(items), 20):
            lines.append("  " + ",".join(f"0x{value:0{digits}X}" for value in items[offset:offset+20]) + ",")
        return "\n".join(lines) + "\n};\n"
    prefix = name.upper().replace("-", "_")
    header = array("uint16_t", f"{prefix}_PALETTE", palette, 4)
    header += array("uint32_t", f"{prefix}_OFFSETS", offsets, 6)
    header += array("uint8_t", f"{prefix}_DATA", data, 2)
    header += (f"static const AnimationAsset {prefix} = "
               f"{{{width}, {height}, {frame_count}, {prefix}_PALETTE, {prefix}_OFFSETS, {prefix}_DATA}};\n")
    metadata = dict(width=width, height=height, frames=frame_count, columns=8,
                    uri="data:image/png;base64," + b64encode(png).decode())
    if period is not None:
        header += f"static constexpr uint32_t {prefix}_PERIOD_MS = {period};\n"
        metadata["period"] = period
        poses = [indexed.crop(((i % 8)*width, (i//8)*height,
                               (i % 8+1)*width, (i//8+1)*height)).convert("RGB")
                 for i in range(frame_count)]
        # GIF timing has 10 ms precision; distribute rounding without drift.
        durations = [(round((i+1)*period/frame_count/10)-round(i*period/frame_count/10))*10
                     for i in range(frame_count)]
        preview_name = "cat-preview.gif" if name == "cat-walk" else f"{name}-preview.gif"
        poses[0].save(asset_dir / preview_name, save_all=True,
                      append_images=poses[1:], duration=durations, loop=0)
    print(f"{name}: {frame_count} frames, {width}x{height}, {len(palette)} colors, {len(data):,} RLE bytes")
    return header, metadata


def main():
    assets, header_parts = {}, []
    cat_frames, cat_period = load_cat_frames()
    header, metadata = pack("cat-walk", cat_frames, cat_period)
    header_parts.append(header)
    assets["cat-walk"] = metadata
    frames = [floating_heart_frame(index/FRAME_COUNT) for index in range(FRAME_COUNT)]
    header, metadata = pack("floating-hearts", frames)
    header_parts.append(header)
    assets["floating-hearts"] = metadata
    video = json.loads((ROOT / "assets/bad-apple-source.json").read_text(encoding="utf-8"))
    with Image.open(ROOT / "assets/bad-apple-source.png") as sheet:
        width, height, columns = video["width"], video["height"], video["columns"]
        frames = [sheet.crop(((i % columns)*width, (i//columns)*height,
                              (i % columns+1)*width, (i//columns+1)*height)).convert("RGB")
                  for i in range(video["frames"])]
    header, metadata = pack("bad-apple", frames, video["period"])
    header_parts.append(header)
    assets["bad-apple"] = metadata
    header = ("// Generated by tools/build_animation_assets.py; do not edit bitmap data.\n"
              "#pragma once\n#include <Arduino.h>\n"
              "struct AnimationAsset {\n"
              "  uint16_t width, height, frameCount;\n"
              "  const uint16_t *palette;\n  const uint32_t *offsets;\n  const uint8_t *data;\n};\n")
    (ROOT / "Hairclip/AnimationAssets.h").write_text(header + "\n".join(header_parts), encoding="utf-8")
    preview = ROOT / "preview.html"
    html = preview.read_text(encoding="utf-8")
    begin, end = "// BEGIN GENERATED ANIMATION ASSETS", "// END GENERATED ANIMATION ASSETS"
    before, separator, tail = html.partition(begin)
    assert separator and end in tail, "Missing asset markers in preview.html"
    tail = tail.partition(end)[2]
    html = before + begin + "\n      const animationAssets = " + json.dumps(assets, separators=(",", ":")) + ";\n      " + end + tail
    preview.write_text(html, encoding="utf-8")
    print("Shared PNG / RGB565 frames generated and decoded successfully.")


if __name__ == "__main__":
    main()
