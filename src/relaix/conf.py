"""Reads the api.conf file — HTTP server and database configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from conta_tools_shared.config import carregar_ini


@dataclass
class ApiConf:
    host: str
    port: int
    bearer_token: str  # empty = service runs without authentication
    db_url: str  # empty = use the local SQLite default (see db.get_database_url)


def load_api_conf(path: Path) -> ApiConf:
    """
    Reads the api.conf file.

    Expected format::

        [api]
        host         = 127.0.0.1
        port         = 8790
        bearer_token = change-this-token   ; empty = no authentication

        [db]
        url = postgresql+psycopg://user:password@localhost:5432/relaix
    """
    if not path.exists():
        raise FileNotFoundError(f"api.conf not found: {path}")

    # carregar_ini lê utf-8-sig (BOM do Notepad já quebrou parse em produção)
    # com fallback cp1252 — padrão do ecossistema.
    cfg = carregar_ini(path)

    api_sec = cfg["api"] if "api" in cfg else {}
    host = api_sec.get("host", "127.0.0.1").strip()
    port_raw = api_sec.get("port", "8790").strip()
    try:
        port = int(port_raw)
    except ValueError:
        raise ValueError(f"Invalid 'port' field in api.conf: {port_raw!r}")
    bearer_token = api_sec.get("bearer_token", "").strip()

    db_sec = cfg["db"] if "db" in cfg else {}
    db_url = db_sec.get("url", "").strip()

    return ApiConf(host=host, port=port, bearer_token=bearer_token, db_url=db_url)
