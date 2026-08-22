"""Caminhos default dos arquivos de status dos loops standalone (execute,
collect) — lidos pelo processo da API (`relaix serve`) em GET /status.
Os três rodam como serviços NSSM separados (DEPLOY.md seção 10), então
precisam de um StatusFile em disco pra se comunicar."""

from __future__ import annotations

from pathlib import Path

DIRETORIO_STATUS = Path.home() / ".conta-tools" / "relaix"
CAMINHO_EXECUTE = DIRETORIO_STATUS / "execute_status.json"
CAMINHO_COLLECT = DIRETORIO_STATUS / "collect_status.json"
