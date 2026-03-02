---
name: page-mapper
description: Map a website or page structure and save as reusable skills. Use when the user asks to map, wrap, document, or learn a site/page layout for future navigation. Supports two modes — site-level discovery (map all pages) and page-level mapping (map one page's selectors).
metadata: {"nanobot":{"emoji":"🗺️","requires":{"env":["DISPLAY"]}}}
---

# Page Mapper

Extract a website or page structure and save as reusable navigation skills.

Two modes: **site discovery** (map the navigation tree) and **page mapping** (map one page's interactive elements).

## Naming Convention

| Prefix | Purpose | Example |
|--------|---------|---------|
| `site-` | Site navigation index | `site-jira`, `site-github` |
| `page-` | Single page selectors | `page-jira-board`, `page-jira-create` |

## Mode 1: Site Discovery

Map the full navigation tree of a site. Do this first before mapping individual pages.

### 1. Navigate to the site's main page

```
browser(url="https://app.example.com", code="document.title")
```

### 2. Extract the navigation tree

```javascript
JSON.stringify({
  title: document.title,
  url: location.href,
  sections: [...document.querySelectorAll('nav, aside, [role="navigation"], .sidebar, header')].map(section => ({
    label: section.getAttribute('aria-label') || section.tagName.toLowerCase(),
    links: [...section.querySelectorAll('a')].slice(0, 30).map(a => ({
      text: a.textContent.trim(),
      href: a.getAttribute('href')
    })).filter(a => a.text && a.href && !a.href.startsWith('javascript:'))
  })).filter(s => s.links.length > 0)
}, null, 2)
```

For sites with dropdown menus or collapsible sections, trigger the hover/click first, then re-run the extraction to capture hidden links.

### 3. Present to user and save

Show the extracted navigation to the user for review before saving. Remove noise (generic footer links, login/logout, cookie banners).

Call `save_skill` with:
- `skill_name`: `site-<name>` (e.g. `site-jira`)
- `skill_description`: describe the site and what pages are covered, e.g. "Jira Cloud navigation map. Use when navigating Jira pages, finding boards, projects, or issue views."
- `skill_content`: the skill body using this template (do NOT include YAML frontmatter, it is added automatically):

```markdown
# <Site Name>

Base URL: <url>
Auth: <how to authenticate, if needed>

## Pages
- **<Page Name>**: <url> — <what it does>
- **<Page Name>**: <url> — <what it does>

## Main Navigation
- <Section label>
  - <Link text>: <href>
```

## Mode 2: Page Mapping

Map one page's interactive elements (forms, buttons, links, selectors).

### 1. Navigate to the page

```
browser(url="https://app.example.com/board", code="document.title + ' — ' + window.location.href")
```

### 2. Extract the page map

```javascript
JSON.stringify({
  title: document.title,
  url: location.href,
  nav: [...document.querySelectorAll('nav a, header a, [role="navigation"] a')].slice(0, 30).map(a => ({
    text: a.textContent.trim(),
    href: a.getAttribute('href'),
    selector: a.id ? '#' + a.id
      : a.getAttribute('data-testid') ? '[data-testid="' + a.getAttribute('data-testid') + '"]'
      : a.getAttribute('aria-label') ? '[aria-label="' + a.getAttribute('aria-label') + '"]'
      : 'a[href="' + a.getAttribute('href') + '"]'
  })).filter(a => a.text),
  forms: [...document.querySelectorAll('form')].map(f => ({
    id: f.id || null,
    action: f.action,
    method: f.method,
    selector: f.id ? '#' + f.id
      : f.getAttribute('action') ? 'form[action="' + f.getAttribute('action') + '"]'
      : null,
    fields: [...f.querySelectorAll('input,select,textarea,button')].map(el => ({
      tag: el.tagName.toLowerCase(),
      type: el.type || null,
      name: el.name || null,
      placeholder: el.placeholder || null,
      selector: el.id ? '#' + el.id
        : el.getAttribute('data-testid') ? '[data-testid="' + el.getAttribute('data-testid') + '"]'
        : el.name ? el.tagName.toLowerCase() + '[name="' + el.name + '"]'
        : null
    })).filter(el => el.selector)
  })),
  buttons: [...document.querySelectorAll('button:not(form button), [role="button"], input[type="submit"]')].slice(0, 30).map(b => ({
    text: b.textContent.trim() || b.value || '',
    selector: b.id ? '#' + b.id
      : b.getAttribute('data-testid') ? '[data-testid="' + b.getAttribute('data-testid') + '"]'
      : b.getAttribute('aria-label') ? '[aria-label="' + b.getAttribute('aria-label') + '"]'
      : null
  })).filter(b => b.text && b.selector),
  links: [...document.querySelectorAll('main a, [role="main"] a, .content a, #content a')].slice(0, 50).map(a => ({
    text: a.textContent.trim(),
    href: a.getAttribute('href'),
    selector: a.id ? '#' + a.id
      : a.getAttribute('data-testid') ? '[data-testid="' + a.getAttribute('data-testid') + '"]'
      : a.getAttribute('aria-label') ? '[aria-label="' + a.getAttribute('aria-label') + '"]'
      : 'a[href="' + a.getAttribute('href') + '"]'
  })).filter(a => a.text && a.href)
}, null, 2)
```

### 3. Review and refine

- Verify selectors make sense. Remove noise (generic footer links, cookie banners).
- For SPAs, scroll or trigger UI state changes, then re-extract to capture dynamic elements.
- For complex pages, extract per section instead of one big dump.

### 4. Present to user and save

Show the extracted map to the user for review before saving. Ask if they want to save, edit, or re-extract.

Call `save_skill` with:
- `skill_name`: `page-<site>-<page>` (e.g. `page-jira-board`)
- `skill_description`: describe the page and its interactive elements, e.g. "Jira board page selectors. Use when interacting with the Jira board — creating issues, filtering, navigating sprints."
- `skill_content`: the skill body using this template (do NOT include YAML frontmatter):

```markdown
# <Page Title>

URL: <page-url>
Part of: site-<name>

## Navigation
- <Label>: `<selector>`

## Forms
### <Form Name> (<form-selector>)
- <Field label>: `<field-selector>` (<type>)
- Submit: `<submit-selector>`

## Actions
- <Button label>: `<selector>`

## Content Links
- <Link text>: `<selector>`

## Usage Examples

### <Common task>
browser(url="<url>", code="<js>")
```

**Never save a skill without user confirmation.**

## Tips

- For SPAs (React, Vue, Angular), prefer `data-testid` or `aria-label` selectors over class names — they survive re-renders.
- If a selector breaks, re-run the extraction to get updated selectors.
- For authenticated pages, log in first, then extract.
- Keep generated skills lean — only include elements the user actually interacts with.
- Start with `site-` discovery, then map individual pages as needed.
- Content inside iframes is not captured by the default extraction. For iframes, navigate to the iframe URL directly. For Shadow DOM, access elements via `element.shadowRoot.querySelectorAll(...)`.
