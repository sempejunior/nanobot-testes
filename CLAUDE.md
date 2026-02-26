# CLAUDE.md — nanobot

## Project

nanobot is an ultra-lightweight personal AI assistant. The guiding principle is **keep it simple** — small codebase, minimal abstractions, no over-engineering.

- **Stack**: Python 3.11+ / FastAPI / aiosqlite / LiteLLM / React 19 / Tailwind CSS 4 / Zustand
- **Entry point**: `nanobot/cli/commands.py` → `gateway` command starts the server
- **Two modes**: filesystem (single-user) and database (multi-user via `--multiuser`)
- **Run dev**: `make dev` (Docker Compose with hot-reload for both Python and frontend)
- **Run tests**: `pytest`
- **Lint**: `ruff check .` (line limit 100, rules: E, F, I, N, W)

## Architecture

```
nanobot/
├── agent/          # Core loop, context builder, memory, skills, subagent
│   └── tools/      # Tool implementations (filesystem, web, browser, cron, mcp…)
├── bus/            # Pub/sub message routing (InboundMessage → Agent → OutboundMessage)
├── channels/       # Chat platform adapters (Telegram, Discord, Slack, WhatsApp…)
├── cli/            # Typer CLI commands
├── config/         # Pydantic schema and loader
├── cron/           # Scheduled task service
├── db/             # Repository protocols + SQLite implementations
├── heartbeat/      # Periodic proactive wake-up
├── providers/      # LLM provider abstraction (LiteLLM, custom, OAuth)
├── session/        # Conversation state management
├── skills/         # Built-in skill definitions (markdown)
├── web/            # FastAPI server + React frontend
│   └── frontend/   # Vite + React + TypeScript
└── utils/          # Small helpers (paths, filenames)
```

### Key design decisions

- **Protocol-based repositories** (`db/repositories.py`): all storage is behind Protocols. SQLite is the current backend; switching to MongoDB requires only new implementations, no interface changes.
- **Dual-mode everywhere**: MemoryStore, SessionManager, SkillsLoader, ContextBuilder all support both filesystem and database mode. Mode is detected at construction.
- **Registry pattern**: providers (`providers/registry.py`) and tools (`agent/tools/registry.py`) use declarative registries instead of if-elif chains.
- **Event bus**: channels publish inbound messages → agent loop processes → publishes outbound → channels deliver. No direct coupling between channels and agent.
- **Lazy initialization**: MCP servers connect on first message, desktop tools register only if DISPLAY is set, browser tool only if CDP port is reachable.

### Dependency flow (no cycles allowed)

```
config ← cli → agent → providers
                 ↓         ↑
               bus ← channels
                 ↓
              session, memory, cron, db
                 ↓
               web (server consumes all above)
```

## Coding principles

### Keep it simple

- Prefer flat code over nested abstractions. Three similar lines > premature abstraction.
- Don't add features, refactoring, or "improvements" beyond what was asked.
- Don't create helpers or utilities for one-time operations.
- Don't design for hypothetical future requirements.

### Single responsibility

- Each module has one job (see Architecture above). Don't put agent logic in web/, don't put DB queries in agent/.
- Each file should have a clear, narrow purpose. If a file grows past ~400 lines, consider splitting.
- Tools are self-contained: one class per tool, inheriting from `Tool` base.
- Channels are self-contained: one file per platform, inheriting from `BaseChannel`.

### Loose coupling

- Depend on protocols, not implementations. Import repository protocols from `db/repositories.py`, not SQLite classes.
- Use `TYPE_CHECKING` blocks for forward references and to break import cycles.
- Use lazy imports inside functions for optional dependencies.
- Pass dependencies through constructors, don't import globals.
- The agent loop should not know about specific channels. The bus decouples them.

### Separation of concerns

- **Config** defines shapes. It does not contain logic.
- **Repositories** handle persistence. They don't know about business rules.
- **Agent loop** orchestrates LLM ↔ tools. It doesn't handle HTTP or WebSocket.
- **Web server** translates HTTP/WS to service calls. It doesn't contain business logic.
- **Channels** translate platform-specific protocols to bus messages. They don't call the agent directly.

## Code style

### Python

- No inline comments. Only module/class/function docstrings where the intent isn't obvious from the name.
- Use type hints everywhere. Prefer `X | None` over `Optional[X]`.
- Use `from __future__ import annotations` in files with forward references.
- Naming: `PascalCase` classes, `snake_case` functions/variables, `UPPER_SNAKE_CASE` constants, `_leading_underscore` private.
- Imports order: stdlib → third-party → local. Use `isort` via ruff.
- Async by default for I/O operations. Sync only for pure computation.
- Errors: let exceptions propagate. Catch only when you can handle them meaningfully. Don't swallow with empty `except: pass`.

### TypeScript (frontend)

- Functional components with hooks. No class components (except ErrorBoundary).
- Zustand for global state. Local state with `useState` for component-only concerns.
- Tailwind utility classes directly on elements. No CSS modules or styled-components.
- API layer in `lib/api.ts` — components never call `fetch` directly.
- Toast for user-facing error feedback. Never swallow errors silently.

### Both

- No dead code. If something is unused, delete it.
- No backwards-compatibility shims (renamed vars, re-exports, `// removed` comments).
- No emojis in code or comments.

## Testing

- Tests live in `tests/` mirroring the source structure.
- Use `pytest` with `pytest-asyncio` (auto mode).
- Mock external dependencies (LLM providers, network calls) with `AsyncMock`.
- Test behavior, not implementation details.
- Name tests `test_<what_it_does>`, not `test_<method_name>`.

## Common tasks

### Adding a new tool

1. Create `nanobot/agent/tools/my_tool.py` with a class inheriting from `Tool`.
2. Implement `name`, `description`, `parameters` (JSON Schema), and `execute()`.
3. Register in `agent/loop.py` `_register_default_tools()` (fs mode) and/or `agent/user_context.py` `build_tool_registry()` (db mode).

### Adding a new LLM provider

1. Add a `ProviderSpec` entry to the `PROVIDERS` list in `providers/registry.py`.
2. Add a corresponding field in `config/schema.py` `ProvidersConfig`.
3. If the provider needs special handling, create a new provider class inheriting from `LLMProvider`.

### Adding a new channel

1. Create `nanobot/channels/my_channel.py` inheriting from `BaseChannel`.
2. Add config class in `config/schema.py` `ChannelsConfig`.
3. Register in `channels/manager.py`.

### Frontend changes

- Components: `nanobot/web/frontend/src/components/`
- API types: `nanobot/web/frontend/src/lib/api.ts`
- Global state: `nanobot/web/frontend/src/lib/store.ts`
- Dev server: `http://localhost:5173` (Vite with HMR)
- Build: `npm run build` in the frontend directory (output goes to `frontend/static/`)
