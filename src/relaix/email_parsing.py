"""Builds the normalized `{"email": {...}}` envelope from a webhook.site
request item of `type: "email"`.

webhook.site already parses the inbound email for us (`sender`, `headers`,
`text_content`/`html_content`) — no MIME parsing happens here. The one thing
it does NOT inline is attachment bytes: `files` only carries metadata
(id/filename/size/content_type), so each attachment is fetched via
webhook.site's own file-download endpoint and embedded as base64 in the
envelope (there is no S3-style signed URL for email attachments, unlike
G-Click's `arquivos[].url` — see
docs/superpowers/specs/2026-08-25-reinf-dl-fluxo-completo.md in
conta-tools-empresas for the consumer-side contract)."""

from __future__ import annotations

import base64
import html as html_module
import re

import requests

from relaix.domain import WebhookSource

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html_module.unescape(_TAG_RE.sub("", text)).strip()


def _header(headers: dict, name: str) -> str | None:
    values = headers.get(name)
    return values[0] if values else None


def _download_attachment(
    source: WebhookSource, request_uuid: str, file_id: str
) -> bytes:
    url = (
        f"{source.api_url.rstrip('/')}/token/{source.channel_id}"
        f"/request/{request_uuid}/download/{file_id}"
    )
    headers = {"Api-Key": source.api_token} if source.api_token else {}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.content


def build_email_envelope(item: dict, source: WebhookSource) -> dict:
    headers = item.get("headers", {})
    body = (
        item.get("text_content") or _strip_html(item.get("html_content") or "") or None
    )

    attachments = []
    for f in item.get("files", []):
        content = _download_attachment(source, item["uuid"], f["id"])
        attachments.append(
            {
                "filename": f.get("filename"),
                "content_type": f.get("content_type"),
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )

    return {
        "email": {
            "from": item.get("sender") or _header(headers, "from"),
            "to": ", ".join(item.get("destinations") or []) or _header(headers, "to"),
            "subject": _header(headers, "subject"),
            "date": _header(headers, "date"),
            "body": body,
            "attachment_names": ", ".join(
                a["filename"] for a in attachments if a["filename"]
            ),
            "attachments": attachments,
        }
    }
