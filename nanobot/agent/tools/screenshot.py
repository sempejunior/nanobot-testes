"""Screenshot tool — captures the desktop and returns the image to the LLM."""

import asyncio
import base64
import os
import shutil
import tempfile
from typing import Any

from nanobot.agent.tools.base import Tool

_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB
_HAS_TESSERACT = shutil.which("tesseract") is not None


class ScreenshotTool(Tool):
    """Capture a screenshot of the virtual desktop."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        parts = [
            "Capture a screenshot of the desktop. "
            "Returns the image for visual analysis. "
            "Use this to see what is currently displayed on screen.",
        ]
        if _HAS_TESSERACT:
            parts.append(
                " Set ocr=true to also extract text from the screen via OCR."
            )
        return "".join(parts)

    @property
    def parameters(self) -> dict[str, Any]:
        props: dict[str, Any] = {
            "region": {
                "type": "string",
                "description": (
                    "Optional region to capture as 'WxH+X+Y' "
                    "(e.g. '800x600+100+50'). Omit for full screen."
                ),
            },
            "grid": {
                "type": "boolean",
                "description": (
                    "Overlay a coordinate grid on the screenshot (lines every 100px "
                    "with labels). Useful for finding click targets. Default: false."
                ),
            },
        }
        if _HAS_TESSERACT:
            props["ocr"] = {
                "type": "boolean",
                "description": (
                    "Extract text from the screenshot using OCR and include it "
                    "in the response. Default: false."
                ),
            }
        return {
            "type": "object",
            "properties": props,
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str | list[dict[str, Any]]:
        display = os.environ.get("DISPLAY")
        if not display:
            return "Error: No DISPLAY environment variable set. Desktop not available."

        region: str | None = kwargs.get("region")
        grid: bool = kwargs.get("grid", False)
        ocr: bool = kwargs.get("ocr", False) and _HAS_TESSERACT

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = ["import", "-display", display, "-window", "root"]
            if region:
                cmd.extend(["-crop", region])
            cmd.append(tmp_path)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode != 0:
                err = stderr.decode().strip() if stderr else "unknown error"
                return f"Error: screenshot capture failed: {err}"

            ocr_text = ""
            if ocr:
                ocr_text = await self._run_ocr(tmp_path)

            if grid:
                await self._draw_grid(tmp_path)

            size = os.path.getsize(tmp_path)
            if size > _MAX_IMAGE_BYTES:
                await self._convert(tmp_path, ["-resize", "50%", "-quality", "85", tmp_path])
                size = os.path.getsize(tmp_path)
            if size > _MAX_IMAGE_BYTES:
                jpg_path = tmp_path.replace(".png", ".jpg")
                await self._convert(tmp_path, ["-quality", "60", jpg_path])
                if os.path.exists(jpg_path):
                    os.replace(jpg_path, tmp_path)

            with open(tmp_path, "rb") as f:
                data = f.read()

            b64 = base64.b64encode(data).decode()
            data_url = f"data:image/png;base64,{b64}"
            size_kb = len(data) // 1024

            text_parts = [f"Screenshot captured ({size_kb} KB)"]
            if grid:
                text_parts.append("Grid overlay: lines every 100px, labels at intersections.")
            if ocr_text:
                text_parts.append(f"--- OCR Text ---\n{ocr_text}")

            return [
                {"type": "text", "text": "\n".join(text_parts)},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _convert(self, src: str, extra_args: list[str]) -> None:
        """Run ImageMagick convert."""
        proc = await asyncio.create_subprocess_exec(
            "convert", src, *extra_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)

    async def _draw_grid(self, path: str) -> None:
        """Draw a coordinate grid on the image using ImageMagick."""
        draw_cmds: list[str] = []
        for x in range(100, 1921, 100):
            draw_cmds.append(f"line {x},0 {x},1080")
        for y in range(100, 1081, 100):
            draw_cmds.append(f"line 0,{y} 1920,{y}")
        for x in range(0, 1921, 200):
            for y in range(0, 1081, 200):
                draw_cmds.append(f"text {x+2},{y+12} '{x},{y}'")

        draw_str = " ".join(draw_cmds)
        proc = await asyncio.create_subprocess_exec(
            "convert", path,
            "-fill", "none", "-stroke", "rgba(255,0,0,0.3)", "-strokewidth", "1",
            "-draw", draw_str,
            "-fill", "rgba(255,0,0,0.7)", "-stroke", "none",
            "-pointsize", "10", "-font", "DejaVu-Sans",
            "-draw", " ".join(
                f"text {x+2},{y+12} '{x},{y}'"
                for x in range(0, 1921, 200) for y in range(0, 1081, 200)
            ),
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)

    async def _run_ocr(self, image_path: str) -> str:
        """Run tesseract OCR on the image and return extracted text."""
        proc = await asyncio.create_subprocess_exec(
            "tesseract", image_path, "stdout", "--psm", "3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        text = stdout.decode(errors="replace").strip() if stdout else ""
        lines = [line for line in text.splitlines() if line.strip()]
        return "\n".join(lines[:100])  # cap at 100 lines
