"""Reads the api.conf file — HTTP server and database configuration."""

from __future__ import annotations

import configparser
import io
from dataclasses import dataclass
from pathlib import Path


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

    cfg = _read_ini(path)

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


def _read_ini(path: Path) -> configparser.ConfigParser:
    """Reads an .ini/.conf tolerating the Notepad BOM and ANSI (cp1252) encodings.

    Inline on purpose (relaix doesn't import conta-tools-shared). A file that exists but can't
    be read raises PermissionError/OSError spelled out, instead of ConfigParser.read swallowing
    it and the caller seeing an empty config. Parse, interpolation and decode errors never
    carry the file's content (it may be the bearer token or the DB password) nor its full path:
    only the file name and the line number.
    """
    cfg = configparser.ConfigParser(  # config-ok: sou o parser inline (relaix não importa o shared)
        inline_comment_prefixes=(";",), interpolation=_NoLeakInterpolation()
    )
    try:
        raw = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return cfg
    except PermissionError as exc:
        raise PermissionError(f"{path} exists but can't be read ({exc.strerror or exc}).") from exc
    except OSError as exc:
        raise OSError(f"{path} can't be read ({exc.strerror or exc}).") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:  # not UTF-8 (Notepad saved as ANSI): fall back to cp1252
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            # the original carries every byte in .object; keep only the offending slice
            raise UnicodeDecodeError(
                "cp1252", raw[exc.start:exc.end], 0, exc.end - exc.start,
                f"invalid byte at position {exc.start} of {path.name}",
            ) from None
    try:
        # newline=None: universal newlines, like the open() inside ConfigParser.read
        cfg.read_file(io.StringIO(text, newline=None), source=path.name)
    except (configparser.MissingSectionHeaderError, configparser.ParsingError) as exc:
        raise _hide_content(exc) from None
    return cfg


def _hide_content(exc: configparser.Error) -> configparser.Error:
    """Same exception (class kept), message without the file's content: ParsingError and
    MissingSectionHeaderError carry the offending line, InterpolationError the whole value."""
    if isinstance(exc, configparser.InterpolationError):
        msg = (f"Value of '{exc.option}' in section [{exc.section}] could not be interpreted "
               "(a literal '%' is written '%%'); the value is not shown.")
        if isinstance(exc, configparser.InterpolationMissingOptionError):
            exc.args = (exc.option, exc.section, "", exc.reference)
        elif isinstance(exc, configparser.InterpolationDepthError):
            exc.args = (exc.option, exc.section, "")
        else:
            exc.args = (exc.option, exc.section, msg)
    else:
        if isinstance(exc, configparser.MissingSectionHeaderError):  # no `.errors`
            exc.line = ""
            exc.args = (exc.source, exc.lineno, "")
            line = exc.lineno
        else:
            exc.errors = [(n, "") for n, _ in exc.errors]
            line = exc.errors[0][0] if exc.errors else "?"
        msg = (f"Syntax error in {exc.source}, line {line}; the line's content is not shown "
               "because it may be a secret.")
    exc.message = msg
    return exc


class _NoLeakInterpolation(configparser.BasicInterpolation):
    """A stray '%' in a value raises InterpolationError whose text carries the rest of the value."""

    def before_get(self, parser, section, option, value, defaults):
        try:
            return super().before_get(parser, section, option, value, defaults)
        except configparser.InterpolationError as exc:
            raise _hide_content(exc) from None
