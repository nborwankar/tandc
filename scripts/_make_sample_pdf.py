"""Generate tests/web/fixtures/sample.pdf with a known sentinel string.

Re-run only when the sentinel changes. Requires reportlab (a one-shot
generator dep — NOT in the project's runtime requirements). Install ad-hoc:

    pip install reportlab

Then:

    python scripts/_make_sample_pdf.py
"""

from pathlib import Path

from reportlab.pdfgen import canvas

SENTINEL = "TANDC SAMPLE PDF - we collect personal data and use arbitration."
TARGET = (
    Path(__file__).resolve().parent.parent / "tests" / "web" / "fixtures" / "sample.pdf"
)


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(TARGET))
    c.drawString(72, 720, SENTINEL)
    c.save()
    size = TARGET.stat().st_size
    print(f"wrote {TARGET} ({size} bytes)")


if __name__ == "__main__":
    main()
