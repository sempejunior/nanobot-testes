# nanobot multi-user

Fork multi-user do [nanobot](https://github.com/HKUDS/nanobot) com frontend web, banco de dados, navegacao web autonoma e ferramentas de desktop.

O nanobot original e um assistente pessoal AI ultra-leve (~4.000 linhas). Este fork extende ele para funcionar como **plataforma multi-tenant completa**: cada usuario tem sessoes, memoria, skills, ferramentas e configuracoes totalmente isoladas. Alem disso, adiciona capacidades de **navegacao web** e **interacao com desktop** que permitem ao agente operar um browser real e usar aplicacoes graficas de forma autonoma.

## O que muda em relacao ao original

| Area | nanobot original | Este fork |
|------|-----------------|-----------|
| **Usuarios** | Single-user (filesystem) | Multi-user com isolamento completo por usuario |
| **Storage** | Arquivos JSON no disco | SQLite com Repository Pattern (8 repositorios) |
| **Frontend** | Sem UI web | React 19 + Tailwind CSS 4 + Zustand (auth, chat, paineis) |
| **Auth** | Sem autenticacao | Registro/login com bearer token JWT |
| **Navegacao Web** | Sem suporte | Browser tool via Chrome DevTools Protocol com stealth patches |
| **Desktop** | Sem suporte | Computer use (xdotool) + Screenshot (ImageMagick + OCR) |
| **Deploy** | `pip install` + CLI | Docker com Chromium, Xvfb, noVNC, hot-reload |

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│                 React Frontend (porta 5173 dev / 18790 prod)     │
│        Auth  |  Chat (streaming)  |  Cron  |  Memory  |  Skills │
│                         Settings  |  Provider por usuario        │
└─────────────────────────┬────────────────────────────────────────┘
                          │ HTTP + WebSocket (bearer token)
┌─────────────────────────▼────────────────────────────────────────┐
│                  FastAPI Web Server (porta 18790)                 │
│  /api/auth/register  /api/auth/login  /api/me                    │
│  /api/sessions       /api/cron        /api/memory                │
│  /api/skills         /api/config      /api/config/provider       │
│  /api/config/mcp     /ws/chat (streaming com tool hints)         │
│  /api/health                                                     │
└───────────┬────────────────────────────────┬─────────────────────┘
            │                                │
    ┌───────▼────────┐              ┌────────▼───────────┐
    │   AgentLoop    │              │ RepositoryFactory   │
    │  (multiuser)   │              │  (SQLite WAL mode)  │
    │                │              │                     │
    │  UserContext    │              │  UserRepository     │
    │  por usuario:  │              │  SessionRepository  │
    │  - sessions    │              │  MessageRepository  │
    │  - memory      │              │  MemoryRepository   │
    │  - skills      │              │  SkillRepository    │
    │  - tools       │              │  CronRepository     │
    │  - provider    │              │  ChannelBinding     │
    │  - rate limits │              │  AuditRepository    │
    └───────┬────────┘              └────────────────────┘
            │
    ┌───────▼────────────────────────────────────────────┐
    │              Tools disponíveis                      │
    │  read_file  write_file  edit_file  list_dir  exec  │
    │  web_search  web_fetch  message  save_skill  cron  │
    │  save_memory  search_memory  MCP tools             │
    │  browser (CDP)  computer (xdotool)  screenshot     │
    └────────────────────────────────────────────────────┘
```

### Stack

- **Backend**: Python 3.12 / FastAPI / aiosqlite / LiteLLM
- **Frontend**: React 19 / TypeScript / Tailwind CSS 4 / Zustand / Vite
- **Navegacao Web**: Chromium com Chrome DevTools Protocol (CDP) + stealth patches
- **Desktop**: xdotool / ImageMagick / Tesseract OCR / Xvfb (virtual display)
- **Infra**: Docker / noVNC / x11vnc / fluxbox

## Quick Start

### Com Docker (recomendado)

**1. Clone o repositorio**

```bash
git clone <repo-url>
cd nanobot
```

**2. Configure o provider LLM**

Crie ou edite `~/.nanobot/config.json`:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

**3. Suba o container**

```bash
make up
```

**4. Acesse o frontend**

Abra `http://localhost:18790` no browser. Registre um usuario e comece a conversar.

### Desenvolvimento com hot-reload

```bash
make dev
```

Isso inicia dois containers:

| Servico | URL | Descricao |
|---------|-----|-----------|
| **Frontend Vite** | `http://localhost:5173` | Hot-reload para alteracoes em `.tsx`, `.ts`, `.css` |
| **API FastAPI** | `http://localhost:18790` | Hot-reload para alteracoes em `.py` (via watchmedo) |
| **noVNC** | `http://localhost:6080/vnc.html` | Desktop virtual com Chromium, xterm, fluxbox |

No modo dev, o Chromium roda com `--remote-debugging-port=9222` e o display virtual esta ativo, entao o browser tool e o computer tool funcionam automaticamente. Voce pode acompanhar visualmente o que o agente esta fazendo pelo noVNC.

## Makefile

| Comando | Descricao |
|---------|-----------|
| `make up` | Inicia em **producao** — frontend compilado + API na porta 18790 + noVNC na 6080 |
| `make dev` | Inicia em **desenvolvimento** — hot-reload para Python (watchmedo) e React (Vite HMR). Abre logs automaticamente |
| `make down` | Para e remove todos os containers e redes |
| `make build` | Reconstroi a imagem Docker do zero (npm build + uv pip install) |
| `make rebuild` | Equivale a `make build` seguido de `make up` |
| `make logs` | Acompanha os logs do container gateway em tempo real |
| `make shell` | Abre um shell bash interativo dentro do container |

## Navegacao Web Autonoma

O agente pode navegar na web de forma autonoma usando o **browser tool**, que se comunica com o Chromium via Chrome DevTools Protocol (CDP). Isso permite:

- **Navegar para qualquer URL**: o agente abre paginas, espera o carregamento e le o conteudo
- **Ler o DOM**: extrair textos, links, tabelas, formularios — tudo via JavaScript
- **Preencher formularios**: setar valores em inputs, selects, textareas
- **Clicar em elementos**: por CSS selector, muito mais confiavel que coordenadas
- **Executar JavaScript arbitrario**: qualquer interacao que o browser suporta
- **Navegar entre paginas**: seguir links, submeter formularios, voltar

### Stealth Patches

O browser tool injeta patches de stealth em toda pagina carregada para evitar deteccao de automacao:

- Remove o flag `navigator.webdriver`
- Simula chrome runtime, plugins e languages
- Corrige WebGL vendor/renderer (fingerprinting)
- Ajusta permissions API e connection RTT
- Configura User-Agent realista

Esses patches sao equivalentes aos do `puppeteer-extra-plugin-stealth` e tornam o browser praticamente indistinguivel de um navegador operado por humano.

### Workflow de navegacao

```
1. browser(code="document.title", url="https://example.com")     -> navega e le titulo
2. browser(code="document.body.innerText")                        -> le texto da pagina
3. browser(code="document.querySelector('#email').value='x@y.z'") -> preenche campo
4. browser(code="document.querySelector('button.submit').click()") -> clica botao
5. screenshot(ocr=true)                                           -> verifica resultado visual
```

## Interacao com Desktop

Alem do browser, o agente pode interagir com qualquer aplicacao grafica no desktop virtual:

### Computer Tool (xdotool)

- **click** / **double_click** — clique em coordenadas (x, y) com botao esquerdo/direito
- **type** — digita texto com clearmodifiers para evitar interferencia
- **key** — pressiona atalhos de teclado (ctrl+l, alt+F4, Return, etc.)
- **scroll** — scroll up/down com numero configuravel de clicks
- **move** — move o cursor para coordenadas especificas
- **wait** — pausa por N segundos (util apos navegacao)
- **window_info** — retorna titulo, tamanho e posicao da janela ativa

### Screenshot Tool

- **Captura de tela** via ImageMagick `import` — captura total ou regiao especifica
- **Grid overlay** — sobrepoe linhas a cada 100px com labels de coordenadas (facilita encontrar alvos de clique)
- **OCR** — extrai texto da tela via Tesseract (util quando o DOM nao esta acessivel)
- **Redimensionamento automatico** — comprime imagens grandes para caber no limite do LLM

### Docker Desktop (noVNC)

O container roda um desktop virtual completo acessivel pelo browser:

```bash
# Producao (inclui noVNC)
make up
# Acesse: http://localhost:6080/vnc.html

# Ou use o docker-compose dedicado para desktop
docker compose -f docker-compose.desktop.yml up -d
# Acesse: http://localhost:6080/vnc.html
# Senha: nanobot
```

| Porta | Servico |
|-------|---------|
| `18790` | nanobot gateway (API + frontend) |
| `6080` | noVNC (desktop no browser) |
| `5900` | VNC direto (para clientes VNC nativos) |

O desktop inclui: Debian Bookworm, XFCE4/Fluxbox, Chromium, xterm, Python 3.12, Node.js 20, nanobot com todas as dependencias.

## Multi-user

Cada usuario tem **isolamento completo**:

- **Sessoes de conversa** independentes (criar, listar, deletar)
- **Memoria de longo prazo** propria — fatos persistentes + historico pesquisavel
- **Skills customizadas** — criar, editar, ativar/desativar skills por usuario
- **Configuracoes do agente** — modelo LLM, max_tokens, temperatura, max_iterations
- **Provider LLM proprio** — cada usuario pode configurar seu proprio provider (OpenRouter, Anthropic, OpenAI, etc.) ou usar o default do servidor
- **MCP servers** — configuracao de servidores MCP por usuario
- **Cron jobs** individuais — agendamento de tarefas com cron expressions ou intervalos
- **Rate limits** por usuario — tokens/dia e requests/minuto
- **Ferramentas habilitaveis** — cada usuario escolhe quais tools estao ativas

### Frontend Web

O frontend React oferece:

- **Autenticacao** — registro e login com bearer token
- **Chat em tempo real** — WebSocket com streaming de resposta e tool hints visuais
- **Sidebar** — lista de sessoes, troca rapida, criar nova conversa
- **Painel de Cron** — criar jobs com cron expression ou intervalo, listar e remover
- **Painel de Memoria** — editor de long-term memory + busca no historico de conversas
- **Painel de Skills** — listar skills (builtin + custom), editar, ativar/desativar, deletar
- **Painel de Settings** — modelo LLM, max_tokens, temperatura, provider proprio, MCP servers

## Database Layer

SQLite com WAL mode e Repository Pattern (8 repositorios):

| Repositorio | Funcao |
|-------------|--------|
| `UserRepository` | Contas, API keys, agent config, usage tracking, rate limits |
| `SessionRepository` | Metadados de sessao (key, status, last_consolidated) |
| `MessageRepository` | Mensagens por sessao (role, content, tool_calls, timestamps) |
| `MemoryRepository` | Memoria de longo prazo (1 por usuario) + historico pesquisavel |
| `SkillRepository` | Skills customizadas por usuario (name, description, content) |
| `CronRepository` | Jobs agendados por usuario (schedule, payload, state) |
| `ChannelBindingRepository` | Mapeamento de IDs externos (Telegram, Discord, etc.) para user_id |
| `AuditRepository` | Audit trail append-only com TTL cleanup |

Todas as interfaces estao definidas como **Protocols** em `db/repositories.py`. A implementacao atual e SQLite (`db/sqlite/`), mas migrar para MongoDB ou Postgres requer apenas implementar as interfaces — sem alterar nenhum codigo de negocio.

## Configuracao

O arquivo de configuracao fica em `~/.nanobot/config.json`. A estrutura de providers, channels e agents segue o mesmo formato do nanobot original.

### Providers suportados

| Provider | Tipo | Obtencao de API Key |
|----------|------|---------------------|
| OpenRouter | Gateway (todos os modelos) | [openrouter.ai](https://openrouter.ai) |
| Anthropic | Claude direto | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | GPT direto | [platform.openai.com](https://platform.openai.com) |
| DeepSeek | DeepSeek direto | [platform.deepseek.com](https://platform.deepseek.com) |
| Groq | LLM + Whisper (transcricao) | [console.groq.com](https://console.groq.com) |
| Gemini | Gemini direto | [aistudio.google.com](https://aistudio.google.com) |
| MiniMax | MiniMax direto | [platform.minimaxi.com](https://platform.minimaxi.com) |
| vLLM | Servidor local (OpenAI-compat) | — |
| Custom | Qualquer endpoint OpenAI-compatible | — |
| AiHubMix | Gateway | [aihubmix.com](https://aihubmix.com) |
| SiliconFlow | Gateway | [siliconflow.cn](https://siliconflow.cn) |
| VolcEngine | Gateway | [volcengine.com](https://www.volcengine.com) |
| DashScope | Qwen | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| Moonshot | Kimi | [platform.moonshot.cn](https://platform.moonshot.cn) |
| Zhipu | GLM | [open.bigmodel.cn](https://open.bigmodel.cn) |

Exemplo de configuracao com OpenRouter:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-20250514"
    }
  }
}
```

### MCP (Model Context Protocol)

Suporte completo a MCP servers. A configuracao e compativel com Claude Desktop / Cursor:

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "remote": {
        "url": "https://example.com/mcp/",
        "headers": { "Authorization": "Bearer xxxxx" },
        "toolTimeout": 120
      }
    }
  }
}
```

Suporta transporte **stdio** (processos locais) e **HTTP** (endpoints remotos). Tools do MCP sao descobertas e registradas automaticamente no startup.

### Channels

Telegram, Discord, WhatsApp, Feishu, Slack, Email, QQ, DingTalk, Mochat. Em modo multi-user, canais sao mapeados a usuarios via `ChannelBindingRepository`. Consulte a [documentacao do nanobot original](https://github.com/HKUDS/nanobot) para configuracao detalhada de cada canal.

## Estrutura do Projeto

```
nanobot/
├── agent/                 Core do agente
│   ├── loop.py            Loop principal (LLM <-> tools), dual-mode (fs/db)
│   ├── context.py         Construtor de prompt do sistema
│   ├── memory.py          Persistencia de memoria (fs/db)
│   ├── skills.py          Carregador de skills (fs/db)
│   ├── subagent.py        Execucao de tarefas em background
│   ├── user_context.py    Contexto isolado por usuario (db mode)
│   └── tools/             Ferramentas do agente
│       ├── browser.py     Navegacao web via Chrome DevTools Protocol
│       ├── computer.py    Controle de desktop via xdotool
│       ├── screenshot.py  Captura de tela + grid + OCR
│       ├── memory.py      Save/search memoria persistente
│       ├── skill.py       Save/update skills customizadas
│       ├── cron.py        Agendamento de tarefas
│       ├── mcp.py         Integracao com MCP servers
│       ├── filesystem.py  Leitura/escrita/edicao de arquivos
│       ├── shell.py       Execucao de comandos
│       ├── web.py         Web search (Brave) + web fetch
│       ├── message.py     Envio de mensagens para canais
│       └── spawn.py       Spawn de subagentes
├── bus/                   Roteamento pub/sub de mensagens
├── channels/              Adaptadores de chat (Telegram, Discord, Slack, ...)
├── cli/                   Comandos CLI (Typer)
├── config/                Schema Pydantic + loader
├── cron/                  Servico de tarefas agendadas (fs/db)
├── db/                    Repository Pattern + SQLite
│   ├── repositories.py    Interfaces (Protocols) — 8 repositorios
│   ├── factory.py         Factory para instanciar repos
│   └── sqlite/            Implementacoes SQLite (connection, migrations, repos)
├── heartbeat/             Wake-up periodico proativo
├── providers/             Abstracacao de providers LLM (registry + LiteLLM)
├── session/               Gerenciamento de sessoes de conversa (fs/db)
├── skills/                Skills builtin (markdown)
│   ├── memory/            Skill de consolidacao de memoria
│   └── desktop-navigation/ Skill de navegacao web e desktop
├── web/                   FastAPI server + React frontend
│   ├── server.py          API REST + WebSocket + auth
│   └── frontend/          Vite + React + TypeScript
│       └── src/
│           ├── components/ AuthPage, ChatArea, Sidebar, Paineis, ...
│           └── lib/        API client, Zustand store, types
├── utils/                 Helpers (paths, filenames)
└── docker/
    ├── entrypoint.sh      Startup: Xvfb + fluxbox + VNC + noVNC + Chromium + nanobot
    └── desktop/           Dockerfile para container desktop dedicado
```

## Testes

```bash
pytest
```

Usa pytest com pytest-asyncio (auto mode). Dependencias externas (LLM, rede) sao mockadas com AsyncMock. Os testes cobrem database layer, session manager, memory store, cron service, agent loop e integracao multi-user.

## Changelog

### Unreleased

- Plataforma multi-user com isolamento completo por usuario (8 repositorios SQLite)
- Frontend web React com autenticacao, chat streaming, e paineis de cron/memory/skills/settings
- Browser tool com navegacao web autonoma via Chrome DevTools Protocol e stealth patches
- Computer use tool com controle de desktop via xdotool (click, type, key, scroll, window_info)
- Screenshot tool com captura de tela, grid de coordenadas e OCR via Tesseract
- Docker setup completo com Chromium, Xvfb, noVNC, fluxbox, hot-reload
- Makefile para ciclo de desenvolvimento e producao
- Desktop navigation skill (documentacao para o agente usar browser + computer tools)
- Rate limiting por usuario (tokens/dia, requests/minuto)
- Provider LLM configuravel por usuario (override do default do servidor)
- MCP servers configuraveis por usuario via painel de settings
- Audit trail com TTL cleanup
- Channel binding para mapeamento multi-user de canais externos

---

Baseado no [nanobot](https://github.com/HKUDS/nanobot) by HKUDS. Licenca MIT.
