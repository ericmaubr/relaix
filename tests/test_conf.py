"""Cobre o wiring do api.conf — em especial BOM do Notepad (bug real de produção ago/2026)."""
from relaix.conf import load_api_conf


def test_load_api_conf_com_bom(tmp_path):
    caminho = tmp_path / "api.conf"
    caminho.write_text("[api]\nhost = 0.0.0.0\nport = 8791\n", encoding="utf-8-sig")
    conf = load_api_conf(caminho)
    assert conf.host == "0.0.0.0"
    assert conf.port == 8791


# --- erros de leitura/parse não podem vazar segredo nem caminho completo (relaix#1) ---
import configparser
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="usa icacls /deny")
def test_conf_sem_leitura_levanta_permissionerror(tmp_path):
    caminho = tmp_path / "api.conf"
    caminho.write_text("[api]\nbearer_token = SEGREDO\n", encoding="utf-8")
    user = os.environ["USERNAME"]
    # (RD) = só ler dados; (R) inclui READ_CONTROL e trava o próprio /remove
    subprocess.run(["icacls", str(caminho), "/deny", f"{user}:(RD)"], check=True, capture_output=True)
    try:
        with pytest.raises(PermissionError, match="exists but can.t be read"):
            load_api_conf(caminho)
    finally:
        subprocess.run(["icacls", str(caminho), "/remove:d", user], check=True, capture_output=True)
    # restaurou de fato: voltou a ser legível
    assert load_api_conf(caminho).bearer_token == "SEGREDO"


def test_conf_ausente_continua_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_api_conf(tmp_path / "nao-existe.conf")


def test_conf_pasta_levanta_oserror_sem_caminho_na_mensagem_de_parse(tmp_path):
    with pytest.raises(OSError):
        load_api_conf(tmp_path)  # existe, mas é uma pasta


@pytest.mark.parametrize("conteudo, vazamentos", [
    ("[db]\nurl = postgresql://u:p%40ss@h/db\n", ["ss@h", "p%40ss", "40ss"]),  # senha URL-encoded
    ("[api]\nbearer_token = SEGREDO%y\n", ["SEGREDO", "%y"]),
])
def test_percent_solto_nao_vaza_valor(tmp_path, conteudo, vazamentos):
    caminho = tmp_path / "api.conf"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(configparser.InterpolationError) as e:
        load_api_conf(caminho)
    msg = str(e.value)
    assert not any(v in msg for v in vazamentos)
    assert str(tmp_path) not in msg


def test_sintaxe_quebrada_nao_vaza_linha_nem_caminho(tmp_path):
    caminho = tmp_path / "api.conf"
    caminho.write_text("bearer_token = SEGREDO\n", encoding="utf-8")  # sem cabeçalho de seção
    with pytest.raises(configparser.MissingSectionHeaderError) as e:
        load_api_conf(caminho)
    msg = str(e.value)
    assert "SEGREDO" not in msg and str(tmp_path) not in msg
    assert "api.conf" in msg and "line 1" in msg

    caminho.write_text("[api]\nlinha sem igual SEGREDO\n", encoding="utf-8")  # sem '='
    with pytest.raises(configparser.ParsingError) as e:
        load_api_conf(caminho)
    msg = str(e.value)
    assert "SEGREDO" not in msg and str(tmp_path) not in msg
    assert "api.conf" in msg and "line 2" in msg


def test_bytes_invalidos_levanta_unicodedecodeerror_sem_conteudo(tmp_path):
    caminho = tmp_path / "api.conf"
    # 0x81 não existe em cp1252; \xff quebra utf-8; SEGREDO ao redor não pode aparecer
    caminho.write_bytes(b"[api]\nbearer_token = SEGREDO\x81\n")
    with pytest.raises(UnicodeDecodeError) as e:
        load_api_conf(caminho)
    assert "SEGREDO" not in str(e.value)
    assert "SEGREDO" not in repr(e.value.object)
    assert str(tmp_path) not in str(e.value)


def test_conf_cp1252_com_acento_ainda_funciona(tmp_path):
    caminho = tmp_path / "api.conf"
    caminho.write_bytes("[api]\nhost = ação\n".encode("cp1252"))
    assert load_api_conf(caminho).host == "ação"
