"""
Provider registry — maps provider IDs to their classes and default configs.

Providers are split into two categories:
  "ai"    — AI/LLM service providers (OpenRouter, OpenAI, Anthropic, etc.)
  "cloud" — Cloud infrastructure providers (Railway, Vercel, AWS, GCP, etc.)
"""

# AI Providers
from providers.openrouter import OpenRouterProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from providers.xai import XAIProvider
from providers.mistral import MistralProvider
from providers.groq import GroqProvider
from providers.manus import ManusProvider
from providers.warp import WarpProvider
from providers.plaud import PlaudProvider
from providers.gemini import GeminiProvider

# Cloud Providers
from providers.railway import RailwayProvider
from providers.vercel import VercelProvider
from providers.mem0 import Mem0Provider
from providers.neon import NeonProvider
from providers.runpod import RunPodProvider
from providers.aws import AWSProvider
from providers.gcp import GCPProvider

# ─── AI Provider Registry ────────────────────────────────────────────────────

AI_PROVIDERS = {
    "openrouter": {
        "class": OpenRouterProvider,
        "name": "OpenRouter",
        "category": "ai",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "sk-or-v1-...", "secret": True},
        ],
        "auth_help": "Get your API key from openrouter.ai/settings/keys",
        "tier": 1,
        "refresh_interval": 300,
    },
    "openai": {
        "class": OpenAIProvider,
        "name": "OpenAI",
        "category": "ai",
        "auth_type": "admin_key",
        "auth_fields": [
            {"key": "api_key", "label": "Admin Key", "placeholder": "sk-admin-...", "secret": True},
        ],
        "auth_help": "Create an Admin key at platform.openai.com/settings/organization/admin-keys",
        "tier": 1,
        "refresh_interval": 300,
        "note": "Shows 30-day spend. No direct balance API available.",
    },
    "anthropic": {
        "class": AnthropicProvider,
        "name": "Anthropic",
        "category": "ai",
        "auth_type": "session_cookie",
        "auth_fields": [
            {"key": "session_cookie", "label": "Session Cookie", "placeholder": "sk-ant-...", "secret": True},
            {"key": "org_id", "label": "Organisation ID", "placeholder": "org-...", "secret": False},
        ],
        "auth_help": "Get sessionKey cookie and org_id from platform.claude.com DevTools → Application → Cookies",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "xai": {
        "class": XAIProvider,
        "name": "xAI (Grok)",
        "category": "ai",
        "auth_type": "management_key",
        "auth_fields": [
            {"key": "api_key", "label": "Management Key", "placeholder": "xai-...", "secret": True},
            {"key": "team_id", "label": "Team ID", "placeholder": "team-...", "secret": False},
        ],
        "auth_help": "Create a Management Key at console.x.ai → Settings → API Keys",
        "tier": 1,
        "refresh_interval": 300,
    },
    "mistral": {
        "class": MistralProvider,
        "name": "Mistral AI",
        "category": "ai",
        "auth_type": "session_cookie",
        "auth_fields": [
            {"key": "session_cookie", "label": "Session Cookie", "placeholder": "Paste cookie string", "secret": True},
        ],
        "auth_help": "Copy session cookies from console.mistral.ai → DevTools → Application → Cookies",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "groq": {
        "class": GroqProvider,
        "name": "Groq",
        "category": "ai",
        "auth_type": "session_cookie",
        "auth_fields": [
            {"key": "session_cookie", "label": "Session Cookie", "placeholder": "Paste cookie string", "secret": True},
        ],
        "auth_help": "Copy session cookies from console.groq.com → DevTools → Application → Cookies",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "manus": {
        "class": ManusProvider,
        "name": "Manus",
        "category": "ai",
        "auth_type": "bearer_token",
        "auth_fields": [
            {"key": "api_key", "label": "JWT Bearer Token", "placeholder": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "secret": True},
        ],
        "auth_help": "Open manus.im → DevTools → Network → filter 'api.manus.im' → copy Authorization header value (after 'Bearer ')",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "warp": {
        "class": WarpProvider,
        "name": "Warp",
        "category": "ai",
        "auth_type": "session_cookie",
        "auth_fields": [
            {"key": "session_cookie", "label": "Session Cookie", "placeholder": "Paste cookie string", "secret": True},
        ],
        "auth_help": "Copy session cookies from app.warp.dev → DevTools → Application → Cookies",
        "tier": 2,
        "refresh_interval": 1800,
    },
    "plaud": {
        "class": PlaudProvider,
        "name": "Plaud",
        "category": "ai",
        "auth_type": "jwt_token",
        "auth_fields": [
            {"key": "api_key", "label": "JWT Token", "placeholder": "eyJ...", "secret": True},
        ],
        "auth_help": "Open web.plaud.ai → DevTools Console → run: localStorage.getItem('tokenstr')",
        "tier": 2,
        "refresh_interval": 3600,
    },
    "gemini": {
        "class": GeminiProvider,
        "name": "Gemini",
        "category": "ai",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "AIza...", "secret": True},
        ],
        "auth_help": "Get your API key from aistudio.google.com/app/apikey",
        "tier": 1,
        "refresh_interval": 300,
        "note": "No balance endpoint — shows key validity and available models.",
    },
}

# ─── Cloud Provider Registry ─────────────────────────────────────────────────

CLOUD_PROVIDERS = {
    "railway": {
        "class": RailwayProvider,
        "name": "Railway",
        "category": "cloud",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Token", "placeholder": "Paste token", "secret": True},
        ],
        "auth_help": "Generate a token at railway.app/account/tokens — set as RAILWAY_CREDIT_TOKEN (not RAILWAY_API_KEY, which Railway injects automatically)",
        "tier": 1,
        "refresh_interval": 600,
    },
    "vercel": {
        "class": VercelProvider,
        "name": "Vercel",
        "category": "cloud",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Token", "placeholder": "Paste token", "secret": True},
            {"key": "team_id", "label": "Team ID (optional)", "placeholder": "team_...", "secret": False},
        ],
        "auth_help": "Generate a token at vercel.com/account/tokens",
        "tier": 1,
        "refresh_interval": 600,
        "note": "Shows month-to-date spend.",
    },
    "mem0": {
        "class": Mem0Provider,
        "name": "mem0",
        "category": "cloud",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "m0-...", "secret": True},
        ],
        "auth_help": "Get your API key from app.mem0.ai/dashboard/api-keys",
        "tier": 1,
        "refresh_interval": 600,
        "note": "No billing API — shows key validity and memory count.",
    },
    "neon": {
        "class": NeonProvider,
        "name": "Neon DB",
        "category": "cloud",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "Paste key", "secret": True},
        ],
        "auth_help": "Generate an API key at console.neon.tech/app/settings/api-keys",
        "tier": 1,
        "refresh_interval": 600,
        "note": "Shows compute hours used. Consumption API requires Launch plan or above.",
    },
    "runpod": {
        "class": RunPodProvider,
        "name": "RunPod",
        "category": "cloud",
        "auth_type": "api_key",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "placeholder": "Paste key", "secret": True},
        ],
        "auth_help": "Generate an API key at runpod.io/console/user/settings → API Keys",
        "tier": 1,
        "refresh_interval": 600,
    },
    "aws": {
        "class": AWSProvider,
        "name": "AWS",
        "category": "cloud",
        "auth_type": "multi_key",
        "auth_fields": [
            {"key": "api_key", "label": "Access Key ID", "placeholder": "AKIA...", "secret": False},
            {"key": "api_secret", "label": "Secret Access Key", "placeholder": "Paste secret", "secret": True},
        ],
        "auth_help": "Create an IAM user with ce:GetCostAndUsage permission at console.aws.amazon.com/iam",
        "tier": 1,
        "refresh_interval": 3600,
        "note": "Shows month-to-date spend via Cost Explorer.",
    },
    "gcp": {
        "class": GCPProvider,
        "name": "GCP",
        "category": "cloud",
        "auth_type": "service_account",
        "auth_fields": [
            {"key": "session_cookie", "label": "Service Account JSON", "placeholder": "Paste full JSON key file contents", "secret": True},
        ],
        "auth_help": "Create a service account with roles/billing.viewer at console.cloud.google.com/iam-admin/serviceaccounts",
        "tier": 1,
        "refresh_interval": 3600,
        "note": "Shows billing account info. Real-time spend requires budget configuration.",
    },
}

# ─── Combined Registry ────────────────────────────────────────────────────────

PROVIDER_REGISTRY = {**AI_PROVIDERS, **CLOUD_PROVIDERS}

__all__ = [
    "PROVIDER_REGISTRY",
    "AI_PROVIDERS",
    "CLOUD_PROVIDERS",
    # AI
    "OpenRouterProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "XAIProvider",
    "MistralProvider",
    "GroqProvider",
    "ManusProvider",
    "WarpProvider",
    "PlaudProvider",
    "GeminiProvider",
    # Cloud
    "RailwayProvider",
    "VercelProvider",
    "Mem0Provider",
    "NeonProvider",
    "RunPodProvider",
    "AWSProvider",
    "GCPProvider",
]
