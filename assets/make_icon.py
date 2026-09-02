"""Genera el icono de GasolinApp.

Gota de combustible resuelta solo con aristas: vertice estrecho arriba, cuerpo
ancho y esquinas biseladas abajo. El corte interior es el nivel de combustible.
"""
from PIL import Image, ImageDraw

AMBER, INK = "#F2A93B", "#14181B"
SIZE = 512

DROP = [(32, 5), (52, 33), (52, 45), (44, 55), (20, 55), (12, 45), (12, 33)]
LEVEL = (19, 41, 45, 47)


def draw_icon(size: int = SIZE) -> Image.Image:
    k = size / 64
    img = Image.new("RGBA", (size, size), AMBER)
    d = ImageDraw.Draw(img)
    d.polygon([(x * k, y * k) for x, y in DROP], fill=INK)
    x0, y0, x1, y1 = LEVEL
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=AMBER)
    return img


if __name__ == "__main__":
    icon = draw_icon()
    icon.save("assets/icon.png")
    icon.resize((180, 180), Image.LANCZOS).save("assets/icon-180.png")
    icon.resize((32, 32), Image.LANCZOS).save("assets/favicon-32.png")
    print("iconos generados")
