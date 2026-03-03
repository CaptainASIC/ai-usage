"""
Provider registry - maps provider IDs to their classes and default configs.
"""

from providers.openrouter import OpenRouterProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from providers.xai import XAIProvider
from providers.mistral import MistralProvider
from providers.groq import GroqProvider
from providers.manus import ManusProvider
from providers.warp import WarpProvider
from providers.plaud import PlaudProvider

# Registry: provider_id -> (ProviderClass, default_config)
PROVIDER_REGISTRY = {
    "openrouter": {
        "class": OpenRouterProvider,
        "name": "OpenRouter",
        "auth_type": "api_key",
        "auth_fields": ["api_key"],
        "auth_help": "Get your API key from openrouter.ai/settings/keys",
        "tier": 1,
        "refresh_interval": 300,
    },
    "openai": {
        "class": OpenAIProvider,
        "name": "OpenAI",
        "auth_type": "admin_key",
        "auth_fields": ["admin_key"],
        "auth_help": "Create an Admin key at platform.openai.com/settings/organization/admin-keys",
        "tier": 1,
        "refresh_interval": 300,
        "note": "Shows 30-day spend. No direct balance API available.",
    },
    "anthropic": {
        "class": AnthropicProvider,
        "name": "Anthropic",
        "auth_type": "session_cookie",
        "auth_fields": ["session_cookie", "org_id"],
        "auth_help": "Get sessionKey cookie and org_id from platform.claude.com DevTools",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "xai": {
        "class": XAIProvider,
        "name": "xAI (Grok)",
        "auth_type": "management_key",
        "auth_fields": ["management_key", "team_id"],
        "auth_help": "Create a Management Key at console.x.ai → Settings",
        "tier": 1,
        "refresh_interval": 300,
    },
    "mistral": {
        "class": MistralProvider,
        "name": "Mistral AI",
        "auth_type": "session_cookie",
        "auth_fields": ["session_cookie"],
        "auth_help": "Copy session cookies from console.mistral.ai DevTools",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "groq": {
        "class": GroqProvider,
        "name": "Groq",
        "auth_type": "session_cookie",
        "auth_fields": ["session_cookie"],
        "auth_help": "Copy session cookies from console.groq.com DevTools",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "manus": {
        "class": ManusProvider,
        "name": "Manus",
        "auth_type": "session_cookie",
        "auth_fields": ["session_cookie"],
        "auth_help": "Copy session cookie or Bearer token from manus.im DevTools",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "warp": {
        "class": WarpProvider,
        "name": "Warp",
        "auth_type": "session_cookie",
        "auth_fields": ["session_cookie"],
        "auth_help": "Copy session cookies from app.warp.dev DevTools",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "plaud": {
        "class": PlaudProvider,
        "name": "Plaud",
        "auth_type": "jwt_token",
        "auth_fields": ["jwt_token"],
        "auth_help": "Open web.plaud.ai → DevTools Console → run: localStorage.getItem('tokenstr')",
        "tier": 2,
        "refresh_interval": 3600,
    },
}

__all__ = [
    "PROVIDER_REGISTRY",
    "OpenRouterProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "XAIProvider",
    "MistralProvider",
    "GroqProvider",
    "ManusProvider",
    "WarpProvider",
    "PlaudProvider",
]
