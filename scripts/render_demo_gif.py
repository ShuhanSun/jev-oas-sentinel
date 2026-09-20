from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "jev-oas-sentinel-demo.gif"
FONT_CANDIDATES = (
    Path(os.environ["JEV_DEMO_FONT"]) if os.environ.get("JEV_DEMO_FONT") else None,
    Path("/System/Library/Fonts/SFNSMono.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
)


def capture_output() -> str:
    executable = ROOT / ".venv" / "bin" / "jev-oas-sentinel"
    command = str(executable) if executable.exists() else shutil.which("jev-oas-sentinel")
    if not command:
        raise RuntimeError("jev-oas-sentinel is not installed; run uv sync --locked first")
    result = subprocess.run(
        [
            command,
            "compare",
            "--base",
            "examples/base-openapi.yaml",
            "--head",
            "examples/head-openapi.yaml",
            "--dry-run",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.replace("⚠️", "[REVIEW]").replace("→", "->")


def render_frame(lines: list[str], status: str) -> Image.Image:
    image = Image.new("RGB", (1400, 860), "#080d1a")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 28, 1372, 832), radius=22, fill="#101827", outline="#2a3650", width=2)
    draw.rounded_rectangle((28, 28, 1372, 94), radius=22, fill="#182238")
    draw.rectangle((28, 72, 1372, 94), fill="#182238")
    for x, color in ((62, "#ff5f57"), (94, "#febc2e"), (126, "#28c840")):
        draw.ellipse((x - 9, 52 - 9, x + 9, 52 + 9), fill=color)

    title_font = _font(25)
    body_font = _font(19)
    small_font = _font(18)
    draw.text((175, 39), "JEV OAS Sentinel — semantic compatibility preview", font=title_font, fill="#dce7ff")

    y = 126
    for line in _visual_lines(lines):
        color = "#d9e2f2"
        if line.startswith("$"):
            color = "#7dd3fc"
        elif "[REVIEW]" in line or "semantic-evaluation-planned" in line:
            color = "#c4a7ff"
        elif line.startswith("|0|1|0|"):
            color = "#86efac"
        draw.text((64, y), line, font=body_font, fill=color)
        y += 27

    draw.text((64, 792), status, font=small_font, fill="#8fa3bf")
    draw.text((1040, 792), "actual CLI output • no API key", font=small_font, fill="#8fa3bf")
    return image


def _visual_lines(lines: list[str], width: int = 112) -> list[str]:
    rendered: list[str] = []
    for source in lines:
        line = source
        while len(line) > width:
            rendered.append(line[:width])
            line = "  " + line[width:]
        rendered.append(line)
    return rendered


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if candidate and candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


def main() -> None:
    output_lines = capture_output().strip().splitlines()
    command_lines = [
        "$ uvx jev-oas-sentinel compare \\",
        "    --base examples/base-openapi.yaml \\",
        "    --head examples/head-openapi.yaml \\",
        "    --dry-run --format markdown",
    ]
    stages = [
        (command_lines[:1], "Type the command"),
        (command_lines, "Dry-run plans JEV calls without making a network request"),
        (command_lines + ["", "Planning semantic evaluations..."], "Inspecting structural and semantic changes"),
        (command_lines + [""] + output_lines[:6], "Structural schema remains compatible"),
        (command_lines + [""] + output_lines, "Consumer-facing prose changed: semantic review planned"),
    ]
    frames = [render_frame(lines, status) for lines, status in stages]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=[900, 1300, 1200, 1600, 4200],
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
