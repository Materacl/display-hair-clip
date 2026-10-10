"""Import a short silent video loop. Requires ffmpeg on PATH and Pillow.

python tools/import_bad_apple.py path/to/badapple.mp4
Then run tools/build_animation_assets.py to update firmware and HTML.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FPS = 15
SIZE = (320, 170)


def crop_top(time, height):
    """A continuous camera move keeps the bouncing apple inside the wide frame."""
    middle = (height-SIZE[1])/2
    keys = [(12.0, 0), (12.4, 0), (12+14/15, 50), (12+22/15, middle)]
    for (start, first), (end, last) in zip(keys, keys[1:]):
        if start <= time < end:
            mix = (time-start)/(end-start)
            mix = mix*mix*(3-2*mix)
            return max(0, min(height-SIZE[1], first+(last-first)*mix))
    return 0 if time < keys[0][0] else middle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    # 12.0 contains the previous throwing hand; it would reappear in the dissolve.
    # Start after it has left the frame, with the apple already fully visible.
    parser.add_argument("--start", type=float, default=12.4)
    parser.add_argument("--duration", type=float, default=6.6)
    parser.add_argument("--overlap", type=float, default=0.4)
    args = parser.parse_args()
    if args.start < 0 or not 0 < args.overlap < args.duration / 2:
        parser.error("Require start >= 0 and 0 < overlap < duration / 2")
    info = json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(args.video),
    ], check=True, stdout=subprocess.PIPE).stdout)["streams"][0]
    picture_size = (SIZE[0], round((info["height"]-8)*SIZE[0]/(info["width"]-8)))
    if picture_size[1] < SIZE[1]:
        raise ValueError("Source video is too wide for this crop")
    # One original image fills the width. No independently generated side layers.
    raw = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(args.start),
        "-i", str(args.video), "-t", str(args.duration), "-an", "-vf",
        f"fps={FPS},crop=iw-8:ih-8,scale={picture_size[0]}:{picture_size[1]}:flags=lanczos,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ], check=True, stdout=subprocess.PIPE).stdout
    stride = picture_size[0] * picture_size[1]
    if len(raw) % stride:
        raise ValueError("Incomplete video frame")
    # Remove faint compression marks in the solid black and white areas.
    contrast = [max(0, min(255, round((value-24)*255/207))) for value in range(256)]
    source = []
    for offset in range(0, len(raw), stride):
        picture = Image.frombytes("L", picture_size, raw[offset:offset+stride]).point(contrast)
        source_time = args.start + (offset//stride)/FPS
        top = crop_top(source_time, picture.height)
        image = picture.transform(SIZE, Image.Transform.EXTENT,
                                  (0, top, picture.width, top+SIZE[1]),
                                  Image.Resampling.BICUBIC)
        source.append(image)
    overlap = round(args.overlap * FPS)
    if overlap < 2 or len(source) <= overlap * 2:
        raise ValueError("Clip too short for the chosen overlap")
    frames = source[overlap:-overlap]
    for index in range(overlap):
        mix = (index + 1) / overlap
        mix = mix * mix * (3 - 2 * mix)
        frames.append(Image.blend(source[-overlap+index], source[index], mix))
    # Across the loop boundary these are adjacent ORIGINAL frames, not a cut.
    assert frames[-1].tobytes() == source[overlap-1].tobytes()
    assert frames[0].tobytes() == source[overlap].tobytes()
    assert len(frames) == len(source) - overlap
    atlas = Image.new("L", (SIZE[0]*8, SIZE[1]*((len(frames)+7)//8)))
    for index, image in enumerate(frames):
        # Sixteen gray levels retain smooth edges without noisy dithering.
        image = image.point(lambda value: round(value / 17) * 17)
        atlas.paste(image, ((index % 8)*SIZE[0], (index//8)*SIZE[1]))
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    atlas.save(assets / "bad-apple-source.png", optimize=True)
    metadata = dict(width=SIZE[0], height=SIZE[1], frames=len(frames), columns=8,
                    fps=FPS, period=round(len(frames)*1000/FPS),
                    start=args.start, duration=args.duration, overlap=args.overlap, borderCrop=4,
                    framing="original video scaled to full width, vertical crop with smooth apple tracking",
                    scaledSize=picture_size,
                    source="https://github.com/bad-apple-lab/Bad-Apple/blob/main/badapple.mp4",
                    sourceSha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
                    credits="Bad Apple!! shadow art PV: Anira; music: Alstroemeria Records / nomico; Touhou: ZUN. No audio included.")
    (assets / "bad-apple-source.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(frames)} frames, {metadata['period']} ms, seamless frame boundary.")


if __name__ == "__main__":
    main()
