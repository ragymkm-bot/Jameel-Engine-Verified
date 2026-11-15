"""Configuration loader for Ragy AI agents."""

import json
from pathlib import Path
from typing import Dict, Any


CONFIG_PATH = Path("/c/RagyAI/config.json")
SECRETS_DIR = Path("/c/RagyAI/Data/Secrets")


def load_config() -> Dict[str, Any]:
    """Load main configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_secrets() -> Dict[str, str]:
    """Load secrets from files in the secrets directory."""
    secrets = {}
    if SECRETS_DIR.exists():
        for secret_file in SECRETS_DIR.glob("*.key"):
            key_name = secret_file.stem
            secrets[key_name] = secret_file.read_text().strip()
    return secrets


def get_agent_config() -> Dict[str, Any]:
    """Build complete configuration for agents."""
    config = load_config()
    secrets = load_secrets()
    
    # Merge with environment variables (highest priority)
    import os
    env_overrides = {
        "n8n_url": os.getenv("N8N_URL", config.get("n8n_endpoint", "http://localhost:5678")),
        "notion_token": os.getenv("NOTION_TOKEN", secrets.get("notion_token")),
        "openrouter_key": os.getenv("OPENROUTER_API_KEY", secrets.get("openrouter_key")),
    }
    
    # Add Notion page IDs from config
    env_overrides.update({
        "notion_research_page": config.get("notion_research_page"),
        "notion_dev_page": config.get("notion_dev_page"),
        "notion_quality_page": config.get("notion_quality_page"),
        "notion_auto_page": config.get("notion_auto_page"),
    })
    
    return env_overrides