"""
یک‌بار اجرا؛ PNGهای خروجی در static/icons کامیت می‌شوند.
وابستگی زمان اجرا نیست (نه در requirements). اجرا: python scripts/make_pwa_icons.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image

ICONS = Path(__file__).resolve().parent.parent / "static" / "icons"
SVG = ICONS / "logo.svg"   # عمداً نه logo-animated.svg (در حالت ثابت خالی رندر می‌شود)


def render_logo(px):
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert نصب نیست: sudo apt install librsvg2-bin")
    out = Path(tempfile.mkdtemp()) / "logo.png"
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px), "-o", str(out), str(SVG)], check=True)
    return Image.open(out).convert("RGBA")


def make(name, size, ratio, bg=None):
    canvas = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    px = round(size * ratio)
    logo = render_logo(px * 2).resize((px, px), Image.LANCZOS)   # ۲ برابر رندر، بعد کوچک‌کردن = لبه‌ی نرم‌تر
    canvas.alpha_composite(logo, ((size - px) // 2, (size - px) // 2))
    if bg:
        canvas = canvas.convert("RGB")   # غیرشفاف
    canvas.save(ICONS / name, optimize=True)
    print("ساخته شد:", name, canvas.size, canvas.mode)


if __name__ == "__main__":
    WHITE = (255, 255, 255, 255)
    make("icon-192.png", 192, 0.84)                    # purpose=any، شفاف
    make("icon-512.png", 512, 0.84)                    # purpose=any، شفاف
    make("icon-maskable-512.png", 512, 0.58, WHITE)    # لوگو داخل safe-zone (وسط ۸۰٪)، زمینه‌ی پر
    make("apple-touch-icon-180.png", 180, 0.72, WHITE) # iOS شفافیت را سیاه می‌کند؛ باید غیرشفاف باشد
