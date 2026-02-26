---
name: memory
description: Two-layer memory system with tool-based recall.
always: true
---

# Memory

## Structure

- **Long-term memory** — Important facts (preferences, project context, relationships). Always loaded into your context.
- **Conversation history** — Append-only event log. NOT loaded into context. Search it with the `search_memory` tool.

## When to Save Memory

Use the `save_memory` tool **proactively** — don't wait for the user to ask "remember this". Save whenever you learn:
- User's name, role, or personal details
- Preferences ("I prefer dark mode", "always use TypeScript")
- Project context ("The API uses OAuth2", "deploy target is AWS")
- Technical decisions or architecture choices
- Tasks the user is working on or planning
- Things the user explicitly asks you to remember

**Rule**: If in doubt, save it. It's better to save something unnecessary than to forget something important.

## Search Past Events

Use the `search_memory` tool to search past conversation history by keyword.
Before asking the user to repeat something, check if you already have it in memory.

## Auto-consolidation

Old conversations are automatically summarized and appended to history when the session grows large. Long-term facts are extracted to memory. You don't need to manage this.
