"""Cobre o wiring do api.conf — em especial BOM do Notepad (bug real de produção ago/2026)."""
from relaix.conf import load_api_conf


def test_load_api_conf_com_bom(tmp_path):
    caminho = tmp_path / "api.conf"
    caminho.write_text("[api]\nhost = 0.0.0.0\nport = 8791\n", encoding="utf-8-sig")
    conf = load_api_conf(caminho)
    assert conf.host == "0.0.0.0"
    assert conf.port == 8791
