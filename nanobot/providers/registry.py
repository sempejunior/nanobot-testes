"""
Provider Registry — single source of truth for LLM provider metadata.

Adding a new provider:
  1. Add a ProviderSpec to PROVIDERS below.
  2. Add a field to ProvidersConfig in config/schema.py.
  Done. Env vars, prefixing, config matching, status display all derive from here.

Order matters — it controls match priority and fallback. Gateways first.
Every entry writes out all fields so you can copy-paste as a template.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    """One LLM provider's metadata. See PROVIDERS below for real examples.

    Placeholders in env_extras values:
      {api_key}  — the user's API key
      {api_base} — api_base from config, or this spec's default_api_base
    """

    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""

    litellm_prefix: str = ""
    skip_prefixes: tuple[str, ...] = ()
    env_extras: tuple[tuple[str, str], ...] = ()

    is_gateway: bool = False
    is_local: bool = False
    detect_by_key_prefix: str = ""
    detect_by_base_keyword: str = ""
    default_api_base: str = ""

    strip_model_prefix: bool = False
    model_overrides: tuple[tuple[str, dict[str, Any]], ...] = ()
    is_oauth: bool = False
    is_direct: bool = False
    supports_prompt_caching: bool = False

    @property
    def label(self) -> str:
        return self.display_name or self.name.title()


PROVIDERS: tuple[ProviderSpec, ...] = (

    ProviderSpec(
        name="custom",
        keywords=(),
        env_key="",
        display_name="Custom",
        litellm_prefix="",
        is_direct=True,
    ),

    ProviderSpec(
        name="openrouter",
        keywords=("openrouter",),
        env_key="OPENROUTER_API_KEY",
        display_name="OpenRouter",
        litellm_prefix="openrouter",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=True,
        is_local=False,
        detect_by_key_prefix="sk-or-",
        detect_by_base_keyword="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        strip_model_prefix=False,
        model_overrides=(),
        supports_prompt_caching=True,
    ),

    ProviderSpec(
        name="aihubmix",
        keywords=("aihubmix",),
        env_key="OPENAI_API_KEY",
        display_name="AiHubMix",
        litellm_prefix="openai",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=True,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="aihubmix",
        default_api_base="https://aihubmix.com/v1",
        strip_model_prefix=True,
        model_overrides=(),
    ),

    ProviderSpec(
        name="siliconflow",
        keywords=("siliconflow",),
        env_key="OPENAI_API_KEY",
        display_name="SiliconFlow",
        litellm_prefix="openai",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=True,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="siliconflow",
        default_api_base="https://api.siliconflow.cn/v1",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="volcengine",
        keywords=("volcengine", "volces", "ark"),
        env_key="OPENAI_API_KEY",
        display_name="VolcEngine",
        litellm_prefix="volcengine",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=True,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="volces",
        default_api_base="https://ark.cn-beijing.volces.com/api/v3",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="anthropic",
        keywords=("anthropic", "claude"),
        env_key="ANTHROPIC_API_KEY",
        display_name="Anthropic",
        litellm_prefix="anthropic",
        skip_prefixes=("anthropic/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
        supports_prompt_caching=True,
    ),

    ProviderSpec(
        name="openai",
        keywords=("openai", "gpt", "o1", "o3", "o4"),
        env_key="OPENAI_API_KEY",
        display_name="OpenAI",
        litellm_prefix="openai",
        skip_prefixes=("openai/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="openai_codex",
        keywords=("openai-codex", "codex"),
        env_key="",
        display_name="OpenAI Codex",
        litellm_prefix="",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="codex",
        default_api_base="https://chatgpt.com/backend-api",
        strip_model_prefix=False,
        model_overrides=(),
        is_oauth=True,
    ),

    ProviderSpec(
        name="github_copilot",
        keywords=("github_copilot", "copilot"),
        env_key="",
        display_name="Github Copilot",
        litellm_prefix="github_copilot",
        skip_prefixes=("github_copilot/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
        is_oauth=True,
    ),

    ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        litellm_prefix="deepseek",
        skip_prefixes=("deepseek/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="gemini",
        keywords=("gemini",),
        env_key="GEMINI_API_KEY",
        display_name="Gemini",
        litellm_prefix="gemini",
        skip_prefixes=("gemini/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="zhipu",
        keywords=("zhipu", "glm", "zai"),
        env_key="ZAI_API_KEY",
        display_name="Zhipu AI",
        litellm_prefix="zai",
        skip_prefixes=("zhipu/", "zai/", "openrouter/", "hosted_vllm/"),
        env_extras=(
            ("ZHIPUAI_API_KEY", "{api_key}"),
        ),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="dashscope",
        keywords=("qwen", "dashscope"),
        env_key="DASHSCOPE_API_KEY",
        display_name="DashScope",
        litellm_prefix="dashscope",
        skip_prefixes=("dashscope/", "openrouter/"),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="moonshot",
        keywords=("moonshot", "kimi"),
        env_key="MOONSHOT_API_KEY",
        display_name="Moonshot",
        litellm_prefix="moonshot",
        skip_prefixes=("moonshot/", "openrouter/"),
        env_extras=(
            ("MOONSHOT_API_BASE", "{api_base}"),
        ),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="https://api.moonshot.ai/v1",
        strip_model_prefix=False,
        model_overrides=(
            ("kimi-k2.5", {"temperature": 1.0}),
        ),
    ),

    ProviderSpec(
        name="minimax",
        keywords=("minimax",),
        env_key="MINIMAX_API_KEY",
        display_name="MiniMax",
        litellm_prefix="minimax",
        skip_prefixes=("minimax/", "openrouter/"),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="https://api.minimax.io/v1",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="vllm",
        keywords=("vllm",),
        env_key="HOSTED_VLLM_API_KEY",
        display_name="vLLM/Local",
        litellm_prefix="hosted_vllm",
        skip_prefixes=(),
        env_extras=(),
        is_gateway=False,
        is_local=True,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),

    ProviderSpec(
        name="groq",
        keywords=("groq",),
        env_key="GROQ_API_KEY",
        display_name="Groq",
        litellm_prefix="groq",
        skip_prefixes=("groq/",),
        env_extras=(),
        is_gateway=False,
        is_local=False,
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        default_api_base="",
        strip_model_prefix=False,
        model_overrides=(),
    ),
)


def find_by_model(model: str) -> ProviderSpec | None:
    """Match a standard provider by model-name keyword (case-insensitive).
    Skips gateways/local — those are matched by api_key/api_base instead."""
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")
    model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
    normalized_prefix = model_prefix.replace("-", "_")
    std_specs = [s for s in PROVIDERS if not s.is_gateway and not s.is_local]

    for spec in std_specs:
        if model_prefix and normalized_prefix == spec.name:
            return spec

    for spec in std_specs:
        if any(kw in model_lower or kw.replace("-", "_") in model_normalized for kw in spec.keywords):
            return spec
    return None


def find_gateway(
    provider_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ProviderSpec | None:
    """Detect gateway/local provider.

    Priority:
      1. provider_name — if it maps to a gateway/local spec, use it directly.
      2. api_key prefix — e.g. "sk-or-" → OpenRouter.
      3. api_base keyword — e.g. "aihubmix" in URL → AiHubMix.

    A standard provider with a custom api_base (e.g. DeepSeek behind a proxy)
    will NOT be mistaken for vLLM — the old fallback is gone.
    """
    if provider_name:
        spec = find_by_name(provider_name)
        if spec and (spec.is_gateway or spec.is_local):
            return spec

    for spec in PROVIDERS:
        if spec.detect_by_key_prefix and api_key and api_key.startswith(spec.detect_by_key_prefix):
            return spec
        if spec.detect_by_base_keyword and api_base and spec.detect_by_base_keyword in api_base:
            return spec

    return None


def find_by_name(name: str) -> ProviderSpec | None:
    """Find a provider spec by config field name, e.g. "dashscope"."""
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None
