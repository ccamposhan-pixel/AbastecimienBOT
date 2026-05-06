from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class ConfigurationError(RuntimeError):
    pass


def load_env_file(path: Path | str = DEFAULT_ENV_FILE) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        loaded[key] = value
        os.environ.setdefault(key, value)

    return loaded


def _required(name: str, allow_blank: bool = False) -> str:
    value = os.environ.get(name)
    if value is None or (not allow_blank and value.strip() == ""):
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value.strip()


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _path(name: str) -> Path:
    value = Path(_required(name))
    if value.is_absolute():
        return value
    return PROJECT_ROOT / value


def _int(name: str) -> int:
    try:
        return int(_required(name))
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be an integer") from exc


def _float(name: str) -> float:
    try:
        return float(_required(name))
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be a float") from exc


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    codex_mode: str
    anthropic_api_key: str
    anthropic_model: str
    google_api_key: str
    gemini_model: str
    data_source: str
    stock_file: Path
    orders_file: Path
    consumption_file: Path
    homologation_file: Path
    lead_time_days: int
    safety_buffer_days: int
    spike_multiplier: float
    price_deviation_pct: float
    overstock_ratio: float
    overstock_days: int

    @classmethod
    def load(cls, env_file: Path | str = DEFAULT_ENV_FILE) -> "Settings":
        load_env_file(env_file)
        return cls(
            llm_provider=_optional("LLM_PROVIDER", "codex").lower(),
            codex_mode=_optional("CODEX_MODE", "workspace"),
            anthropic_api_key=_optional("ANTHROPIC_API_KEY"),
            anthropic_model=_optional("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            google_api_key=_optional("GOOGLE_API_KEY"),
            gemini_model=_optional("GEMINI_MODEL", "gemini-1.5-pro"),
            data_source=_required("DATA_SOURCE"),
            stock_file=_path("STOCK_FILE"),
            orders_file=_path("ORDERS_FILE"),
            consumption_file=_path("CONSUMPTION_FILE"),
            homologation_file=_path("HOMOLOGATION_FILE"),
            lead_time_days=_int("LEAD_TIME_DAYS"),
            safety_buffer_days=_int("SAFETY_BUFFER_DAYS"),
            spike_multiplier=_float("SPIKE_MULTIPLIER"),
            price_deviation_pct=_float("PRICE_DEVIATION_PCT"),
            overstock_ratio=_float("OVERSTOCK_RATIO"),
            overstock_days=_int("OVERSTOCK_DAYS"),
        )

    @property
    def file_paths(self) -> dict[str, Path]:
        return {
            "stock": self.stock_file,
            "purchase_orders": self.orders_file,
            "consumption": self.consumption_file,
            "homologation": self.homologation_file,
        }


settings = Settings.load()
