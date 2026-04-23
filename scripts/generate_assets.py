from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DIR = BASE_DIR / "sample_docs"
PRD_DIR = BASE_DIR / "prd"
TECH_DIR = BASE_DIR / "technical_writeup"


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    PRD_DIR.mkdir(parents=True, exist_ok=True)
    TECH_DIR.mkdir(parents=True, exist_ok=True)

    create_clean_invoice()
    create_messy_bol()
    create_pdf_from_markdown(PRD_DIR / "PRD_GoComet_Nova.md", PRD_DIR / "PRD_GoComet_Nova.pdf")
    create_pdf_from_markdown(
        TECH_DIR / "Technical_Writeup_GoComet_Nova.md",
        TECH_DIR / "Technical_Writeup_GoComet_Nova.pdf",
    )


def create_clean_invoice() -> None:
    lines = [
        "COMMERCIAL INVOICE",
        "",
        "Invoice Number: INV-2024-0042",
        "Consignee Name: ACME Corp",
        "HS Code: 8471.30",
        "Port of Loading: Shanghai",
        "Port of Discharge: Nhava Sheva",
        "Incoterms: CIF",
        "Description of Goods: Laptop computers",
        "Gross Weight: 450 KG",
    ]
    create_text_pdf(SAMPLE_DIR / "clean_invoice.pdf", lines)
    (SAMPLE_DIR / "clean_invoice.pdf.ocr.txt").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def create_messy_bol() -> None:
    lines = [
        "BILL OF LADING - LOW QUALITY SCAN",
        "",
        "Invoice Number: INV-2024-0042",
        "Consignee Name: ACME Corp",
        "HS Code: ",
        "Port of Loading: Shanghai",
        "Port of Discharge: Mumbai",
        "Incoterms: CIF",
        "Description of Goods: Laptop computers",
        "Gross Weight: 450 KG",
        "",
        "Stamp overlap and blur near HS Code",
    ]
    image = render_page(lines, width=1500, height=2100, font_size=32, tint=(244, 238, 225))
    image = image.rotate(-1.5, expand=True, fillcolor=(238, 232, 220))
    draw = ImageDraw.Draw(image)
    draw.ellipse((980, 360, 1320, 700), outline=(150, 40, 40), width=10)
    draw.line((180, 480, 1360, 560), fill=(80, 80, 80), width=7)
    output = SAMPLE_DIR / "messy_bol.jpg"
    image.save(output, "JPEG", quality=72)
    (SAMPLE_DIR / "messy_bol.jpg.ocr.txt").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def create_pdf_from_markdown(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    pages = paginate(text)
    rendered_pages = [
        render_page(page_lines, width=1654, height=2339, font_size=24, tint=(255, 252, 246))
        for page_lines in pages
    ]
    rendered_pages[0].save(
        destination,
        "PDF",
        save_all=True,
        append_images=rendered_pages[1:],
        resolution=150.0,
    )


def paginate(text: str, lines_per_page: int = 42) -> list[list[str]]:
    cleaned = [line.rstrip() for line in text.splitlines()]
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in cleaned:
        if len(current) >= lines_per_page:
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def render_page(
    lines: list[str],
    *,
    width: int,
    height: int,
    font_size: int,
    tint: tuple[int, int, int],
) -> Image.Image:
    image = Image.new("RGB", (width, height), tint)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
        title_font = ImageFont.truetype("arialbd.ttf", font_size + 8)
    except OSError:
        font = ImageFont.load_default()
        title_font = font

    y = 100
    for index, line in enumerate(lines):
        current_font = title_font if index == 0 else font
        draw.text((100, y), line, fill=(24, 26, 31), font=current_font)
        y += font_size + 16
    return image


def create_text_pdf(destination: Path, lines: list[str]) -> None:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    contents = ["BT", "/F1 16 Tf", "72 760 Td", "18 TL"]
    for index, line in enumerate(lines):
        if index == 0:
            contents.append("/F1 20 Tf")
        elif index == 1:
            contents.append("/F1 16 Tf")
        if index > 0:
            contents.append("T*")
        contents.append(f"({escape(line)}) Tj")
    contents.append("ET")
    stream = "\n".join(contents).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
    )
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objects.append(
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    destination.write_bytes(pdf)


if __name__ == "__main__":
    main()
