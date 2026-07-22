"""CLI: python -m relaix serve"""

from __future__ import annotations

import argparse
from pathlib import Path

from relaix.cli._common import add_db_arguments, configure_db


def main_serve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="relaix serve")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--api-token",
        metavar="TOKEN",
        help=(
            "Bearer token required on the endpoints. Alternative: api.conf "
            "([api] bearer_token) or env RELAIX_API_TOKEN. Without a token, "
            "runs without authentication."
        ),
    )
    add_db_arguments(parser)
    args = parser.parse_args(argv)
    configure_db(args)

    host = args.host or "127.0.0.1"
    port = args.port or 8790
    api_token = args.api_token

    conf_path: Path = args.conf
    if conf_path and conf_path.exists():
        from relaix.conf import load_api_conf

        conf = load_api_conf(conf_path)
        host = args.host or conf.host
        port = args.port or conf.port
        api_token = api_token or (conf.bearer_token or None)

    import uvicorn

    from relaix.http_server import app, set_api_token

    if api_token:
        set_api_token(api_token)

    print(f"Starting HTTP API on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
    return 0
