"""Configuration schema using Pydantic."""

from dataclasses import dataclass, field as dc_field
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class WhatsAppConfig(Base):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    proxy: str | None = None
    reply_to_message: bool = False


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class DingTalkConfig(Base):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    allow_from: list[str] = Field(default_factory=list)


class DiscordConfig(Base):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377


class EmailConfig(Base):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False

    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    auto_reply_enabled: bool = True
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)


class MochatMentionConfig(Base):
    """Mochat mention behavior configuration."""

    require_in_groups: bool = False


class MochatGroupRule(Base):
    """Mochat per-group mention requirement."""

    require_mention: bool = False


class MochatConfig(Base):
    """Mochat channel configuration."""

    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"
    reply_delay_ms: int = 120000


class SlackDMConfig(Base):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"
    allow_from: list[str] = Field(default_factory=list)


class SlackConfig(Base):
    """Slack channel configuration."""

    enabled: bool = False
    mode: str = "socket"
    webhook_path: str = "/slack/events"
    bot_token: str = ""
    app_token: str = ""
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    group_policy: str = "mention"
    group_allow_from: list[str] = Field(default_factory=list)
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(Base):
    """QQ channel configuration using botpy SDK."""

    enabled: bool = False
    app_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(Base):
    """Configuration for chat channels."""

    send_progress: bool = True
    send_tool_hints: bool = False
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)


class HeartbeatConfig(Base):
    """Heartbeat service configuration."""

    enabled: bool = True
    interval_s: int = 30 * 60


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)


class WebSearchConfig(Base):
    """Web search tool configuration."""

    api_key: str = ""
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    tool_timeout: int = 30


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class Config(BaseSettings):
    """Root configuration for nanobot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from nanobot.providers.registry import PROVIDERS

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from nanobot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    model_config = ConfigDict(env_prefix="NANOBOT_", env_nested_delimiter="__")


@dataclass
class ServerConfig:
    """Server-wide configuration shared across all users.

    Per-user settings (model, limits, tools_enabled, bootstrap)
    are stored in the ``users`` table in the database.
    """

    providers: ProvidersConfig
    gateway: GatewayConfig
    channels: ChannelsConfig
    tools: ToolsConfig
    default_agent: AgentDefaults = dc_field(default_factory=AgentDefaults)

    @classmethod
    def from_config(cls, config: "Config") -> "ServerConfig":
        """Extract server-level config from the full Config object."""
        return cls(
            providers=config.providers,
            gateway=config.gateway,
            channels=config.channels,
            tools=config.tools,
            default_agent=config.agents.defaults,
        )
