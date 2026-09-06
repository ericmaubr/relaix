"""Wiring ponta a ponta api.conf -> configure_db -> db.get_database_url —
a classe do bug real do conta-tools-nfts ("serve" ignorava [db] url,
mascarado porque todo teste pré-chamava set_database_url). Incerto nº 3 da
fase LLM da auditoria do ecossistema (2026-09)."""

from __future__ import annotations

import argparse

from relaix import db
from relaix.cli._common import configure_db


def _args(**kw):
    return argparse.Namespace(db_url=kw.get("db_url"), conf=kw.get("conf"))


def _reset_db(monkeypatch):
    monkeypatch.setattr(db, "_database_url_override", None)
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_conf_db_url_chega_ao_db_sem_estado_preparado(tmp_path, monkeypatch):
    _reset_db(monkeypatch)
    conf = tmp_path / "api.conf"
    conf.write_text(
        "[api]\nhost = 127.0.0.1\nport = 8790\n\n[db]\nurl = sqlite:///do_conf.db\n",
        encoding="utf-8",
    )
    configure_db(_args(conf=conf))
    assert db.get_database_url() == "sqlite:///do_conf.db"


def test_db_url_cli_tem_precedencia_sobre_conf(tmp_path, monkeypatch):
    _reset_db(monkeypatch)
    conf = tmp_path / "api.conf"
    conf.write_text("[db]\nurl = sqlite:///do_conf.db\n", encoding="utf-8")
    configure_db(_args(db_url="sqlite:///da_cli.db", conf=conf))
    assert db.get_database_url() == "sqlite:///da_cli.db"
