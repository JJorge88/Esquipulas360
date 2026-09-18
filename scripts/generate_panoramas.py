"""Deterministic 2:1 equirectangular calibration images, never location photos."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "static" / "panoramas"
WIDTH, HEIGHT = 2048, 1024

def generate(name, top, bottom, line, title):
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        amount = y / (HEIGHT - 1)
        color = tuple(round(a * (1 - amount) + b * amount) for a, b in zip(top, bottom))
        draw.line((0, y, WIDTH, y), fill=color)
    for degree in range(0, 361, 15):
        x = round(degree / 360 * WIDTH)
        draw.line((x, 0, x, HEIGHT), fill=line, width=2 if degree % 90 == 0 else 1)
    for latitude in range(-90, 91, 15):
        y = round((90 - latitude) / 180 * HEIGHT)
        draw.line((0, y, WIDTH, y), fill="#fece57" if latitude == 0 else line, width=4 if latitude == 0 else 1)
    normal = ImageFont.load_default(size=24)
    large = ImageFont.load_default(size=44)
    for x, label in [(0, "180° / COSTURA"), (512, "+90°"), (1024, "0° / FRENTE"), (1536, "-90°")]:
        # The seam label is split at the wrap; all other labels are centered.
        anchor = "la" if x == 0 else "ma"
        draw.text((x + (8 if x == 0 else 0), 430), label, font=large, fill="#fbf9f6", anchor=anchor)
        draw.text((x + (8 if x == 0 else 0), 545), title, font=normal, fill="#fece57", anchor=anchor)
        draw.text((x + (8 if x == 0 else 0), 585), "DEMO / NO ES UN LUGAR REAL", font=normal, fill="#fbf9f6", anchor=anchor)
        for lat, text in [(60, "ARRIBA +60°"), (30, "+30°"), (-30, "-30°"), (-60, "ABAJO -60°")]:
            y = round((90 - lat) / 180 * HEIGHT)
            draw.text((x + (8 if x == 0 else 0), y + 12), text, font=normal, fill="#fbf9f6", anchor=anchor)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"demo-{name}.png"
    image.save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}: {WIDTH} × {HEIGHT}, {path.stat().st_size // 1024} KiB")

if __name__ == "__main__":
    generate("azul", (15, 39, 60), (31, 80, 93), (64, 110, 128), "ESCENA AZUL")
    generate("ambar", (73, 42, 27), (135, 84, 40), (169, 119, 65), "ESCENA AMBAR")
