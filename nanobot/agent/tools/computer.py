"""Computer tool — interact with the desktop via xdotool."""

import asyncio
import os
from typing import Any

from nanobot.agent.tools.base import Tool

_ACTIONS = ("click", "double_click", "type", "key", "scroll", "move", "wait", "window_info")


class ComputerTool(Tool):
    """Click, type, scroll, and press keys on the virtual desktop."""

    @property
    def name(self) -> str:
        return "computer"

    @property
    def description(self) -> str:
        return (
            "Interact with the graphical desktop: click, double-click, type text, "
            "press key combos, scroll, move the mouse, wait for content to load, "
            "or get info about the active window. "
            "Use the 'screenshot' tool first to see the screen and find coordinates."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(_ACTIONS),
                    "description": (
                        "The action to perform. "
                        "'wait' pauses for a number of seconds (useful after page navigation). "
                        "'window_info' returns the title, size and position of the active window."
                    ),
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate (for click, double_click, move).",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate (for click, double_click, move).",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type (for 'type' action).",
                },
                "key": {
                    "type": "string",
                    "description": (
                        "Key combo to press (for 'key' action), e.g. "
                        "'Return', 'ctrl+l', 'alt+F4'."
                    ),
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "middle", "right"],
                    "description": "Mouse button (default: left).",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Scroll direction (for 'scroll' action).",
                },
                "clicks": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Number of scroll clicks (default: 3).",
                },
                "seconds": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 10,
                    "description": "Seconds to wait (for 'wait' action, default: 2).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        display = os.environ.get("DISPLAY")
        if not display:
            return "Error: No DISPLAY environment variable set. Desktop not available."

        action: str = kwargs["action"]
        if action not in _ACTIONS:
            return f"Error: Unknown action '{action}'. Must be one of {_ACTIONS}."

        env = {**os.environ, "DISPLAY": display}

        try:
            if action == "move":
                return await self._move(kwargs, env)
            elif action == "click":
                return await self._click(kwargs, env)
            elif action == "double_click":
                return await self._double_click(kwargs, env)
            elif action == "type":
                return await self._type(kwargs, env)
            elif action == "key":
                return await self._key(kwargs, env)
            elif action == "scroll":
                return await self._scroll(kwargs, env)
            elif action == "wait":
                return await self._wait(kwargs)
            elif action == "window_info":
                return await self._window_info(env)
        except Exception as e:
            return f"Error: {e}"
        return "Error: unhandled action"

    async def _run(self, args: list[str], env: dict) -> str:
        proc = await asyncio.create_subprocess_exec(
            "xdotool", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            err = stderr.decode().strip() if stderr else "unknown error"
            return f"Error: xdotool failed: {err}"
        return stdout.decode().strip() if stdout else ""

    async def _move(self, kw: dict, env: dict) -> str:
        x, y = kw.get("x"), kw.get("y")
        if x is None or y is None:
            return "Error: 'move' requires x and y."
        err = await self._run(["mousemove", str(x), str(y)], env)
        return err if err.startswith("Error") else f"Moved mouse to ({x}, {y})."

    async def _click(self, kw: dict, env: dict) -> str:
        x, y = kw.get("x"), kw.get("y")
        button = {"left": "1", "middle": "2", "right": "3"}.get(kw.get("button", "left"), "1")
        cmds: list[list[str]] = []
        if x is not None and y is not None:
            cmds.append(["mousemove", str(x), str(y)])
        cmds.append(["click", button])
        for cmd in cmds:
            result = await self._run(cmd, env)
            if result.startswith("Error"):
                return result
        pos = f" at ({x}, {y})" if x is not None else ""
        return f"Clicked{pos}."

    async def _double_click(self, kw: dict, env: dict) -> str:
        x, y = kw.get("x"), kw.get("y")
        button = {"left": "1", "middle": "2", "right": "3"}.get(kw.get("button", "left"), "1")
        cmds: list[list[str]] = []
        if x is not None and y is not None:
            cmds.append(["mousemove", str(x), str(y)])
        cmds.append(["click", "--repeat", "2", "--delay", "80", button])
        for cmd in cmds:
            result = await self._run(cmd, env)
            if result.startswith("Error"):
                return result
        pos = f" at ({x}, {y})" if x is not None else ""
        return f"Double-clicked{pos}."

    async def _type(self, kw: dict, env: dict) -> str:
        text = kw.get("text")
        if not text:
            return "Error: 'type' requires text."
        result = await self._run(["type", "--clearmodifiers", "--delay", "12", text], env)
        return result if result.startswith("Error") else f"Typed {len(text)} characters."

    async def _key(self, kw: dict, env: dict) -> str:
        key = kw.get("key")
        if not key:
            return "Error: 'key' requires a key combo."
        result = await self._run(["key", "--clearmodifiers", key], env)
        return result if result.startswith("Error") else f"Pressed {key}."

    async def _scroll(self, kw: dict, env: dict) -> str:
        direction = kw.get("direction", "down")
        clicks = kw.get("clicks", 3)
        btn = "4" if direction == "up" else "5"
        result = await self._run(["click", "--repeat", str(clicks), btn], env)
        return result if result.startswith("Error") else f"Scrolled {direction} ({clicks} clicks)."

    async def _wait(self, kw: dict) -> str:
        seconds = min(float(kw.get("seconds", 2)), 10)
        await asyncio.sleep(seconds)
        return f"Waited {seconds}s."

    async def _window_info(self, env: dict) -> str:
        wid = await self._run(["getactivewindow"], env)
        if wid.startswith("Error"):
            return wid
        name = await self._run(["getactivewindow", "getwindowname"], env)
        geo = await self._run(["getactivewindow", "getwindowgeometry"], env)
        return f"Active window: {name}\n{geo}"
