"""Inline copy of conta_tools_shared.status (build_status + StatusFile) —
relaix is INDEPENDENT and must not depend on conta_tools_shared (explicit
decision, 2026-09-05/06). Drift against the shared originals is watched by
the ecosystem audit (item 21, conta-tools-shared/scripts/auditoria/espelhos.py):
when the originals evolve, the shared pre-commit forces a review here.

`StatusFile` exists so the collect/execute NSSM loops (separate processes)
report their last cycle to the `relaix serve` process, which exposes it via
GET /status. Timestamps are LOCAL naive time (ecosystem convention 2026-09-06;
the panel's JS parses no-suffix ISO as local, correct on the same machine).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def build_status(
    *,
    last_run_at: str | None = None,
    last_run_ok: bool | None = None,
    last_error: str | None = None,
    counters: dict | None = None,
    detail_url: str | None = None,
    pacote: str | None = None,
) -> dict:
    resultado = {
        "alive": True,
        "last_run_at": last_run_at,
        "last_run_ok": last_run_ok,
        "last_error": last_error,
        "counters": counters or {},
        "detail_url": detail_url,
    }
    if pacote is not None:
        try:
            from importlib.metadata import version

            resultado["versao"] = version(pacote)
        except Exception:
            resultado["versao"] = "dev"
    return resultado


class StatusFile:
    def __init__(self, path: Path):
        self._path = path

    def registrar(self, *, ok: bool, erro: str | None = None, counters: dict | None = None) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "last_run_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "last_run_ok": ok,
            "last_error": erro,
            "counters": counters or {},
        }
        self._path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    def ler(self) -> dict | None:
        if not self._path.exists():
            return None
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):  # silencio-ok: arquivo de status corrompido/ausente = sem status, por contrato
            return None
