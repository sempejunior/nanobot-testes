"""Browser tool — execute JavaScript in the active browser tab via Chrome DevTools Protocol."""

import asyncio
import json
from typing import Any

import httpx

from nanobot.agent.tools.base import Tool

_CDP_HOST = "localhost"
_CDP_PORT = 9222
_CDP_URL = f"http://{_CDP_HOST}:{_CDP_PORT}"

_STEALTH_JS = r"""
(() => {
  // 1. Hide navigator.webdriver
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

  // 2. Fake chrome runtime (missing in headless/automation mode)
  if (!window.chrome) window.chrome = {};
  if (!window.chrome.runtime) {
    window.chrome.runtime = {
      connect: () => {},
      sendMessage: () => {},
      onMessage: { addListener: () => {}, removeListener: () => {} },
    };
  }

  // 3. Fake plugins (headless has 0 plugins)
  Object.defineProperty(navigator, 'plugins', {
    get: () => {
      const plugins = [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer',
          description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
          description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin',
          description: '' },
      ];
      plugins.refresh = () => {};
      return plugins;
    },
  });

  // 4. Fake languages
  Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
  });

  // 5. Spoof permissions API (automation mode returns 'denied' for notifications)
  const origQuery = Notification.permission
    ? window.Notification.requestPermission
    : null;
  try {
    const originalQuery = window.navigator.permissions.query.bind(
      window.navigator.permissions
    );
    window.navigator.permissions.query = (params) => {
      if (params.name === 'notifications') {
        return Promise.resolve({ state: Notification.permission });
      }
      return originalQuery(params);
    };
  } catch (_) {}

  // 6. Fix broken WebGL vendor/renderer (gives away headless)
  const getParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function (param) {
    if (param === 37445) return 'Google Inc. (Intel)';
    if (param === 37446) return 'ANGLE (Intel, Mesa Intel(R) UHD Graphics, OpenGL 4.6)';
    return getParameter.call(this, param);
  };

  // 7. Prevent iframe detection of contentWindow mismatch
  try {
    const elementDescriptor = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype, 'offsetHeight'
    );
    if (elementDescriptor) {
      Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', elementDescriptor);
    }
  } catch (_) {}

  // 8. Fix connection-rtt (0 in headless)
  try {
    if (navigator.connection && navigator.connection.rtt === 0) {
      Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    }
  } catch (_) {}
})();
"""


def cdp_available() -> bool:
    """Check if a CDP-enabled browser is reachable (non-async, for registration time)."""
    import socket
    try:
        with socket.create_connection((_CDP_HOST, _CDP_PORT), timeout=0.5):
            return True
    except OSError:
        return False


class BrowserTool(Tool):
    """Execute JavaScript in the active browser tab."""

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Execute JavaScript code in the active browser tab and return the result. "
            "Use this to read page content, fill forms, click elements by CSS selector, "
            "get the current URL, or interact with the DOM. "
            "Much faster and more reliable than visual coordinate-based clicking for web pages."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "JavaScript code to execute in the page context. "
                        "The last expression's value is returned. "
                        "Examples: "
                        "'document.title', "
                        "'document.querySelector(\"#email\").value = \"user@test.com\"', "
                        "'document.querySelector(\"form\").submit()', "
                        "'window.location.href', "
                        "'[...document.querySelectorAll(\"a\")].map(a => a.href)'"
                    ),
                },
                "url": {
                    "type": "string",
                    "description": (
                        "Navigate to this URL before executing code. "
                        "Omit to run code on the current page."
                    ),
                },
                "wait": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": (
                        "Seconds to wait after navigation before executing code (default: 1). "
                        "Only used when 'url' is provided."
                    ),
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> str:
        code: str = kwargs["code"]
        url: str | None = kwargs.get("url")
        wait: float = float(kwargs.get("wait", 1))

        try:
            ws_url = await self._get_ws_url()
        except Exception as e:
            return (
                f"Error: Cannot connect to browser CDP on port {_CDP_PORT}. "
                f"Make sure Chromium was started with --remote-debugging-port={_CDP_PORT}. "
                f"Details: {e}"
            )

        try:
            import websockets
            async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
                msg_id = 1

                await ws.send(json.dumps({
                    "id": msg_id,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": _STEALTH_JS},
                }))
                await self._recv_result(ws, msg_id)
                msg_id += 1

                await ws.send(json.dumps({
                    "id": msg_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": _STEALTH_JS, "returnByValue": True},
                }))
                await self._recv_result(ws, msg_id)
                msg_id += 1

                if url:
                    await ws.send(json.dumps({
                        "id": msg_id,
                        "method": "Page.navigate",
                        "params": {"url": url},
                    }))
                    msg_id += 1
                    await self._recv_result(ws, msg_id - 1)
                    await asyncio.sleep(wait)

                await ws.send(json.dumps({
                    "id": msg_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": code,
                        "returnByValue": True,
                        "awaitPromise": True,
                        "timeout": 10_000,
                    },
                }))
                result = await self._recv_result(ws, msg_id)

        except Exception as e:
            return f"Error executing JavaScript: {e}"

        if "error" in result:
            return f"CDP error: {result['error'].get('message', result['error'])}"

        eval_result = result.get("result", {})
        exception = eval_result.get("exceptionDetails")
        if exception:
            text = exception.get("text", "")
            exc_obj = exception.get("exception", {})
            desc = exc_obj.get("description", exc_obj.get("value", ""))
            return f"JavaScript error: {text} {desc}".strip()

        value = eval_result.get("result", {})
        val_type = value.get("type", "undefined")
        if val_type == "undefined":
            return "(undefined — code executed successfully)"
        if val_type in ("string", "number", "boolean"):
            return str(value.get("value", ""))
        if "value" in value:
            return json.dumps(value["value"], indent=2, ensure_ascii=False, default=str)
        if "description" in value:
            return value["description"]
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)

    async def _get_ws_url(self) -> str:
        """Get the WebSocket debugger URL of the first browser tab."""
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{_CDP_URL}/json")
            resp.raise_for_status()
            tabs = resp.json()

        for tab in tabs:
            if tab.get("type") == "page" and "webSocketDebuggerUrl" in tab:
                return tab["webSocketDebuggerUrl"]
        if tabs and "webSocketDebuggerUrl" in tabs[0]:
            return tabs[0]["webSocketDebuggerUrl"]
        raise RuntimeError("No browser tab found with CDP WebSocket URL")

    async def _recv_result(self, ws, msg_id: int, timeout: float = 15) -> dict:
        """Read WebSocket messages until we get the response for our msg_id."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == msg_id:
                return msg
        raise TimeoutError(f"CDP response for id={msg_id} not received within {timeout}s")
