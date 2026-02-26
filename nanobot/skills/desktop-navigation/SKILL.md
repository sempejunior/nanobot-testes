---
name: desktop-navigation
description: Navigate the desktop, open browsers, click elements, fill forms, and interact with GUI applications using browser, screenshot, and computer tools.
metadata: {"nanobot":{"emoji":"🖥️","requires":{"env":["DISPLAY"]}}}
---

# Desktop Navigation

You have access to a virtual desktop with a display, browser, and input tools.

## Tools

- **browser** — Execute JavaScript in the active browser tab via CDP. Best for web interaction: read DOM, fill forms, click by CSS selector, navigate. Much faster than visual clicking.
- **screenshot** — Capture what's on screen. Use for visual verification.
  - `grid=true` — Overlay coordinate grid for finding click targets.
  - `ocr=true` — Extract text via OCR.
  - `region="WxH+X+Y"` — Capture only a region.
- **computer** — Physical input: click, type, scroll, key press, wait, window_info. Use for non-browser desktop apps.
- **exec** — Launch applications.

## Web Navigation (use `browser` tool)

### Navigate to a page
```
browser(url="https://example.com", code="document.title")
```

### Read page content
```
browser(code="document.body.innerText")
browser(code="document.title + ' — ' + window.location.href")
```

### Fill forms
```
browser(code="document.querySelector('#email').value = 'user@test.com'")
browser(code="document.querySelector('#password').value = 'secret123'")
browser(code="document.querySelector('form').submit()")
```

### Click elements by selector
```
browser(code="document.querySelector('button.submit').click()")
browser(code="document.querySelector('a[href=\"/login\"]').click()")
```

### Select dropdowns
```
browser(code="const s = document.querySelector('select#country'); s.value = 'BR'; s.dispatchEvent(new Event('change', {bubbles: true}))")
```

### Check checkboxes
```
browser(code="document.querySelector('input[name=\"agree\"]').click()")
```

### Extract data
```
browser(code="[...document.querySelectorAll('table tr')].map(r => [...r.cells].map(c => c.innerText))")
browser(code="[...document.querySelectorAll('a')].map(a => ({text: a.innerText, href: a.href}))")
```

### Wait for element
```
browser(code="new Promise(r => { const check = () => document.querySelector('.result') ? r(document.querySelector('.result').innerText) : setTimeout(check, 200); check(); })")
```

## Desktop Apps (use `computer` + `screenshot`)

For non-browser applications (terminal, file manager, etc.):

1. `screenshot()` — See current state
2. `computer(action="click", x=640, y=300)` — Click at coordinates
3. `computer(action="type", text="hello")` — Type text
4. `computer(action="key", key="ctrl+s")` — Press key combos
5. `computer(action="wait", seconds=2)` — Wait for load
6. `computer(action="window_info")` — Get active window title

## When to use which tool

| Task | Tool |
|------|------|
| Navigate to URL | `browser(url="...")` |
| Read page text | `browser(code="document.body.innerText")` |
| Fill input field | `browser(code="...value = '...'")` |
| Click web button | `browser(code="...click()")` |
| Select dropdown | `browser(code="...value = '...'; dispatchEvent(...)` |
| Submit form | `browser(code="...submit()")` |
| Check current URL | `browser(code="window.location.href")` |
| See the screen | `screenshot()` |
| Find coordinates | `screenshot(grid=true)` |
| Click desktop app | `computer(action="click", ...)` |
| Type in desktop app | `computer(action="type", ...)` |
| Open application | `exec(command="...")` |

## Tips

- Prefer `browser` over `computer` for web pages — it's faster and more reliable.
- Use `screenshot` to visually verify after important actions.
- For React/SPA forms, dispatch events after setting values:
  `el.value = 'x'; el.dispatchEvent(new Event('input', {bubbles: true}))`
- Add `--no-sandbox` when launching Chromium in a container.
- `browser(url="...")` navigates and waits 1s by default. Adjust with `wait` param.
