"""Centralised settings — all config lives here, loaded from .env"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database — default reads from env directly so tests work without .env
    database_url: str = "postgresql://user:password@localhost:5432/mydatabase"

    # JWT
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # Stripe
    stripe_secret_key: str = "sk_test_placeholder"
    stripe_webhook_secret: str = "whsec_placeholder"
    stripe_publishable_key: str = "pk_test_placeholder"

    # App
    app_env: str = "development"
    # Comma-separated list, or "*" to allow any origin (auth uses JWT Bearer
    # headers, not cookies, so a wildcard is safe). Deployed frontends (Zeabur,
    # Vercel, Render) live on different origins than the API.
    allowed_origins: str = "*"

    # Google OAuth 2.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8001/api/auth/google/callback"

    # Frontend URL (used to redirect back after OAuth / external links)
    frontend_url: str = "http://localhost:3000"

    # Salesforce REST integration (JWT bearer flow)
    sf_client_id: str = ""
    sf_client_secret: str = ""
    sf_username: str = ""
    sf_private_key: str = ""
    sf_login_url: str = "https://login.salesforce.com"
    sf_instance_url: str = ""

    # Agentic AI (OpenAI function/tool calling)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Base URL for OpenAI-compatible providers (free options: Groq, OpenRouter, Ollama, ...).
    # Leave empty to use the official OpenAI API.
    openai_base_url: str = ""

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
