"""Gera imagens de exemplo da escala, com nomes fictícios, em assets/escalas.

Substitua pelas imagens reais da escala no servidor (SCHEDULE_IMAGES_DIR), sem versioná-las.
Uso: python scripts/gerar_imagens_exemplo.py  (requer Pillow)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "escalas"
DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
SHIFTS = {
    "manha": ["M12", "M34", "M56"],
    "tarde": ["T12", "T34", "T56"],
    "noite": ["N12", "N34"],
}
TITLES = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}
NAMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "X"]


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for folder in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu"):
        path = Path(folder) / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_shift(shift: str, slots: list[str]) -> Image.Image:
    cell_w, cell_h, first_w, header_h = 170, 64, 110, 120
    width = first_w + cell_w * len(DAYS)
    height = header_h + cell_h * (len(slots) + 1) + 50
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width, header_h], fill="#1f3a5f")
    draw.text((24, 28), f"Escala de plantão - {TITLES[shift]}", fill="white", font=font(30, True))
    draw.text((24, 74), "EXEMPLO: nomes fictícios", fill="#c9d6e8", font=font(18))

    y = header_h
    draw.rectangle([0, y, width, y + cell_h], fill="#e8eef6")
    for index, day in enumerate(DAYS):
        draw.text((first_w + index * cell_w + 16, y + 20), day, fill="#1f3a5f", font=font(20, True))

    for row, slot in enumerate(slots, start=1):
        top = header_h + row * cell_h
        if row % 2 == 0:
            draw.rectangle([0, top, width, top + cell_h], fill="#f6f8fb")
        draw.text((20, top + 20), slot, fill="#1f3a5f", font=font(20, True))
        for column in range(len(DAYS)):
            name = NAMES[(row * 3 + column * 2 + len(shift)) % len(NAMES)]
            color = "#9aa5b1" if name == "X" else "#222222"
            draw.text((first_w + column * cell_w + 16, top + 20), name, fill=color, font=font(20))

    for row in range(len(slots) + 2):
        line_y = header_h + row * cell_h
        draw.line([0, line_y, width, line_y], fill="#d0d7e1", width=1)
    draw.text((20, height - 36), "X = ninguém de plantão no horário", fill="#6b7785", font=font(16))
    return image


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for shift, slots in SHIFTS.items():
        draw_shift(shift, slots).save(OUTPUT / f"{shift}.png", optimize=True)
        print(f"Gerado: {OUTPUT / f'{shift}.png'}")


if __name__ == "__main__":
    main()
