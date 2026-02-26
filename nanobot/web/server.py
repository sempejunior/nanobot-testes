"""nanobot web server — FastAPI backend for the chat interface."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

_STATIC_DIR = Path(__file__).parent / "frontend" / "static"


async def _ensure_db(app_state: Any, data_dir: Path) -> bool:
    """Check DB health; reconnect if the connection died.

    Returns True when repos are usable, False otherwise.
    """
    if not hasattr(app_state, "db") or app_state.db is None:
        return hasattr(app_state, "repos") and app_state.repos is not None

    try:
        await app_state.db.execute("SELECT 1")
        return True
    except Exception:
        pass

    logger.warning("SQLite connection lost — reconnecting…")
    try:
        from nanobot.db.sqlite.connection import create_database
        from nanobot.db.factory import create_sqlite_factory

        db_path = data_dir / "nanobot.db"
        db = await create_database(db_path)
        repos = create_sqlite_factory(db)
        app_state.db = db
        app_state.repos = repos
        logger.info("SQLite connection restored")
        return True
    except Exception as exc:
        logger.error("Failed to reconnect SQLite: {}", exc)
        return False


def create_app(*, config: Any, provider: Any, data_dir: Path) -> FastAPI:
    """Factory: build the FastAPI application."""

    app = FastAPI(title="nanobot", docs_url=None, redoc_url=None)


    @app.on_event("startup")
    async def startup():
        if hasattr(app.state, "agent"):
            logger.info("Using injected dependencies for web server")
            return

        from nanobot.db.sqlite.connection import create_database
        from nanobot.db.factory import create_sqlite_factory
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus
        from nanobot.cron.service import CronService

        db_path = data_dir / "nanobot.db"
        db = await create_database(db_path)
        repos = create_sqlite_factory(db)
        bus = MessageBus()
        cron = CronService(cron_repo=repos.cron)

        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            max_iterations=config.agents.defaults.max_tool_iterations,
            memory_window=config.agents.defaults.memory_window,
            brave_api_key=config.tools.web.search.api_key or None,
            exec_config=config.tools.exec,
            cron_service=cron,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            mcp_servers=config.tools.mcp_servers,
            channels_config=config.channels,
            repos=repos,
        )

        await cron.start()

        app.state.db = db
        app.state.repos = repos
        app.state.agent = agent
        app.state.cron = cron
        app.state.bus = bus
        logger.info("Web server started — DB at {}", db_path)

    @app.on_event("shutdown")
    async def shutdown():
        if hasattr(app.state, "cron"):
            app.state.cron.stop()
        if hasattr(app.state, "agent"):
            await app.state.agent.close_mcp()
        if hasattr(app.state, "db") and app.state.db is not None:
            try:
                await app.state.db.close()
            except Exception:
                pass

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    def _get_user_id(request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        raise HTTPException(401, "Missing or invalid Authorization header")

    async def _require_user(request: Request) -> dict[str, Any]:
        uid = _get_user_id(request)
        try:
            user = await app.state.repos.users.get_by_id(uid)
        except (ValueError, RuntimeError):
            if await _ensure_db(app.state, data_dir):
                user = await app.state.repos.users.get_by_id(uid)
            else:
                raise HTTPException(503, "Database unavailable")
        if not user:
            raise HTTPException(401, "User not found")
        return user

    @app.post("/api/auth/register")
    async def register(request: Request):
        body = await request.json()
        uid = body.get("user_id", "").strip()
        if not uid:
            raise HTTPException(400, "user_id is required")

        repos = app.state.repos
        if await repos.users.get_by_id(uid):
            raise HTTPException(409, "User already exists")

        await repos.users.create({
            "user_id": uid,
            "display_name": body.get("display_name", uid),
            "email": body.get("email"),
            "agent_config": {
                "model": config.agents.defaults.model,
                "max_tokens": config.agents.defaults.max_tokens,
                "temperature": config.agents.defaults.temperature,
                "max_tool_iterations": config.agents.defaults.max_tool_iterations,
                "memory_window": config.agents.defaults.memory_window,
            },
        })
        await repos.channel_bindings.bind(uid, "web", uid)

        user = await repos.users.get_by_id(uid)
        return {"token": uid, "user": _safe_user(user)}

    @app.post("/api/auth/login")
    async def login(request: Request):
        body = await request.json()
        uid = body.get("user_id", "").strip()
        if not uid:
            raise HTTPException(400, "user_id is required")

        user = await app.state.repos.users.get_by_id(uid)
        if not user:
            raise HTTPException(404, "User not found")

        return {"token": uid, "user": _safe_user(user)}

    @app.get("/api/me")
    async def get_me(request: Request):
        user = await _require_user(request)
        return _safe_user(user)

    @app.get("/api/sessions")
    async def list_sessions(request: Request):
        user = await _require_user(request)
        uid = user["user_id"]
        repos = app.state.repos
        sessions = await repos.sessions.list_sessions(uid)
        result = []
        for s in sessions:
            title = "New Chat"
            try:
                msgs = await repos.messages.get_messages(s["id"], limit=1)
                if msgs:
                    content = msgs[0].get("content", "")
                    title = content[:60] + ("..." if len(content) > 60 else "")
            except Exception:
                pass
            result.append({
                "session_key": s["session_key"],
                "title": title,
                "message_count": s.get("message_count", 0),
                "updated_at": s.get("updated_at", ""),
            })
        return result

    @app.get("/api/sessions/{session_key:path}/messages")
    async def get_messages(request: Request, session_key: str):
        user = await _require_user(request)
        uid = user["user_id"]
        repos = app.state.repos
        session = await repos.sessions.get(uid, session_key)
        if not session:
            return []
        msgs = await repos.messages.get_messages(session["id"], limit=200)
        return [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in msgs
        ]

    @app.delete("/api/sessions/{session_key:path}")
    async def delete_session(request: Request, session_key: str):
        user = await _require_user(request)
        uid = user["user_id"]
        ok = await app.state.repos.sessions.delete(uid, session_key)
        return {"ok": ok}

    @app.get("/api/cron")
    async def list_cron(request: Request):
        user = await _require_user(request)
        jobs = await app.state.cron.list_jobs(user_id=user["user_id"], include_disabled=True)
        return [
            {
                "id": j.id, "name": j.name, "enabled": j.enabled,
                "schedule_kind": j.schedule.kind,
                "schedule_expr": j.schedule.expr or (
                    f"every {(j.schedule.every_ms or 0) // 1000}s"
                    if j.schedule.kind == "every" else ""
                ),
                "message": j.payload.message,
            }
            for j in jobs
        ]

    @app.post("/api/cron")
    async def add_cron(request: Request):
        user = await _require_user(request)
        body = await request.json()
        from nanobot.cron.types import CronSchedule

        kind = body.get("kind", "every")
        if kind == "every":
            sched = CronSchedule(kind="every", every_ms=int(body.get("every_seconds", 3600)) * 1000)
        elif kind == "cron":
            sched = CronSchedule(kind="cron", expr=body.get("expr", "0 9 * * *"), tz=body.get("tz"))
        else:
            raise HTTPException(400, "Invalid schedule kind")

        job = await app.state.cron.add_job(
            name=body.get("name", "Web job"),
            schedule=sched,
            message=body.get("message", ""),
            user_id=user["user_id"],
        )
        return {"id": job.id, "name": job.name}

    @app.delete("/api/cron/{job_id}")
    async def delete_cron(request: Request, job_id: str):
        user = await _require_user(request)
        ok = await app.state.cron.remove_job(job_id, user_id=user["user_id"])
        return {"ok": ok}

    @app.get("/api/config")
    async def get_config(request: Request):
        user = await _require_user(request)
        return user.get("agent_config", {})

    @app.put("/api/config")
    async def update_config(request: Request):
        user = await _require_user(request)
        body = await request.json()
        current = user.get("agent_config", {})
        current.update(body)
        await app.state.repos.users.update(user["user_id"], {"agent_config": current})
        if hasattr(app.state, "agent") and hasattr(app.state.agent, "_user_contexts"):
            app.state.agent._user_contexts.pop(user["user_id"], None)
        return {"ok": True, "agent_config": current}

    @app.get("/api/config/provider")
    async def get_provider_config(request: Request):
        user = await _require_user(request)
        provider = user.get("agent_config", {}).get("provider", {})
        masked = dict(provider)
        key = masked.get("api_key", "")
        if key:
            masked["api_key"] = (
                f"{'•' * max(0, len(key) - 4)}{key[-4:]}"
                if len(key) > 4 else "••••"
            )
        return masked

    @app.put("/api/config/provider")
    async def update_provider_config(request: Request):
        user = await _require_user(request)
        body = await request.json()
        agent_cfg = user.get("agent_config", {})
        current = agent_cfg.get("provider", {})
        new_key = body.get("api_key", "")
        if "•" in new_key:
            body["api_key"] = current.get("api_key", "")
        agent_cfg["provider"] = {
            "name": body.get("name", ""),
            "api_key": body.get("api_key", ""),
            "api_base": body.get("api_base", ""),
        }
        await app.state.repos.users.update(user["user_id"], {"agent_config": agent_cfg})
        if hasattr(app.state, "agent") and hasattr(app.state.agent, "_user_contexts"):
            app.state.agent._user_contexts.pop(user["user_id"], None)
        return {"ok": True}

    @app.get("/api/config/mcp")
    async def get_mcp_config(request: Request):
        user = await _require_user(request)
        agent_cfg = user.get("agent_config", {})
        return {"mcpServers": agent_cfg.get("mcp_servers", {})}

    @app.put("/api/config/mcp")
    async def update_mcp_config(request: Request):
        user = await _require_user(request)
        body = await request.json()
        new_servers = body.get("mcpServers", {})

        agent_cfg = user.get("agent_config", {})
        agent_cfg["mcp_servers"] = new_servers
        await app.state.repos.users.update(user["user_id"], {"agent_config": agent_cfg})

        try:
            from nanobot.config.schema import MCPServerConfig
            parsed = {k: MCPServerConfig.model_validate(v) for k, v in new_servers.items()}
            await app.state.agent.reload_mcp(parsed)
        except Exception as e:
            logger.warning("MCP reload failed (config saved anyway): {}", e)

        return {"ok": True}

    @app.get("/api/skills")
    async def get_skills(request: Request):
        user = await _require_user(request)
        return {"tools_enabled": user.get("tools_enabled", [])}

    @app.put("/api/skills")
    async def update_skills(request: Request):
        user = await _require_user(request)
        body = await request.json()
        tools = body.get("tools_enabled", [])
        await app.state.repos.users.update(user["user_id"], {"tools_enabled": tools})
        return {"ok": True, "tools_enabled": tools}

    @app.get("/api/skills/custom")
    async def get_custom_skills(request: Request):
        user = await _require_user(request)
        skills = await app.state.repos.skills.list_skills(user["user_id"], enabled_only=False)
        return skills

    @app.delete("/api/skills/custom/{name}")
    async def delete_custom_skill(request: Request, name: str):
        user = await _require_user(request)
        ok = await app.state.repos.skills.delete_skill(user["user_id"], name)
        return {"ok": ok}

    @app.put("/api/skills/custom/{name}")
    async def update_custom_skill(request: Request, name: str):
        user = await _require_user(request)
        body = await request.json()
        skill = await app.state.repos.skills.get_skill(user["user_id"], name)
        if not skill:
            raise HTTPException(404, f"Skill '{name}' not found")
        skill["content"] = body.get("content", skill["content"])
        skill["description"] = body.get("description", skill.get("description", ""))
        skill["always_active"] = body.get("always_active", skill.get("always_active", 0))
        skill["enabled"] = body.get("enabled", skill.get("enabled", 1))
        await app.state.repos.skills.save_skill(user["user_id"], skill)
        return {"ok": True}

    @app.get("/api/memory")
    async def get_memory(request: Request):
        user = await _require_user(request)
        uid = user["user_id"]
        repos = app.state.repos
        
        long_term = await repos.memories.get_long_term(uid)
        history = await repos.memories.get_history(uid)
        
        return {
            "long_term": long_term,
            "history": history
        }

    @app.get("/api/memory/search")
    async def search_memory(request: Request, q: str = ""):
        user = await _require_user(request)
        if not q.strip():
            return {"results": []}
        results = await app.state.repos.memories.search_history(user["user_id"], q.strip())
        return {"results": results}

    @app.delete("/api/memory")
    async def clear_memory(request: Request):
        user = await _require_user(request)
        uid = user["user_id"]
        count = await app.state.repos.memories.clear_history(uid)
        return {"ok": True, "deleted": count}

    @app.delete("/api/memory/{entry_id}")
    async def delete_memory(request: Request, entry_id: int):
        user = await _require_user(request)
        uid = user["user_id"]
        ok = await app.state.repos.memories.delete_history(uid, entry_id)
        return {"ok": ok}

    @app.put("/api/memory/long_term")
    async def update_long_term_memory(request: Request):
        user = await _require_user(request)
        uid = user["user_id"]
        body = await request.json()
        content = body.get("content", "")
        await app.state.repos.memories.save_long_term(uid, content)
        return {"ok": True}

    @app.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket):
        await ws.accept()
        token = ws.query_params.get("token", "")
        if not token:
            await ws.send_json({"type": "error", "content": "No token"})
            await ws.close()
            return

        try:
            user = await app.state.repos.users.get_by_id(token)
        except (ValueError, RuntimeError):
            if await _ensure_db(app.state, data_dir):
                user = await app.state.repos.users.get_by_id(token)
            else:
                await ws.send_json({"type": "error", "content": "Database unavailable"})
                await ws.close()
                return
        if not user:
            await ws.send_json({"type": "error", "content": "Invalid token"})
            await ws.close()
            return

        uid = user["user_id"]
        logger.info("WebSocket connected: {}", uid)

        try:
            while True:
                data = await ws.receive_json()
                msg_type = data.get("type", "")

                if msg_type == "message":
                    content = data.get("content", "").strip()
                    session_key = data.get("session_key", f"web:{uuid.uuid4().hex[:12]}")

                    if not content:
                        continue

                    async def on_progress(text: str, *, tool_hint: bool = False) -> None:
                        try:
                            await ws.send_json({
                                "type": "tool_hint" if tool_hint else "progress",
                                "content": text,
                            })
                        except Exception:
                            pass

                    try:
                        response = await app.state.agent.process_direct(
                            content,
                            session_key=session_key,
                            channel="web",
                            chat_id=uid,
                            on_progress=on_progress,
                            user_id=uid,
                        )
                        await ws.send_json({
                            "type": "response",
                            "content": response,
                            "session_key": session_key,
                        })
                    except Exception as e:
                        logger.exception("Chat error for {}", uid)
                        await ws.send_json({"type": "error", "content": str(e)})

                elif msg_type == "ping":
                    await ws.send_json({"type": "pong"})

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: {}", uid)
        except Exception as e:
            logger.exception("WebSocket error for {}: {}", token, e)

    @app.get("/")
    async def root():
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/favicon.ico")
    async def favicon():
        return JSONResponse(content={}, status_code=204)

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


def _safe_user(u: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive fields from user dict."""
    return {
        "user_id": u["user_id"],
        "display_name": u.get("display_name", ""),
        "email": u.get("email"),
        "status": u.get("status", "active"),
    }
