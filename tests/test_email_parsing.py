from __future__ import annotations

import base64

from relaix.domain import WebhookSource
from relaix.email_parsing import build_email_envelope

_SOURCE = WebhookSource(
    id="src-1",
    name="Source",
    kind="webhook_site",
    api_url="https://webhook.site",
    api_token="key-123",
    channel_id="token-abc",
    polling_interval_seconds=300,
    max_content_attempts=3,
    max_dispatch_attempts=3,
    last_processed_cursor=None,
    active=True,
    created_at="",
    updated_at="",
)

_ITEM_NO_ATTACHMENT = {
    "uuid": "req-1",
    "type": "email",
    "sender": "ericmaubr@gmail.com",
    "destinations": ["glick-tarefa@emailhook.site"],
    "headers": {"subject": ["teste"], "date": ["Tue, 25 Aug 2026 16:16:33 -0300"]},
    "text_content": "corpo do e-mail.\r\nbla\r\n",
    "html_content": "<div>corpo do e-mail.<div>bla</div></div>",
    "files": [],
}

_ITEM_WITH_ATTACHMENT = {
    **_ITEM_NO_ATTACHMENT,
    "uuid": "req-2",
    "text_content": None,
    "html_content": None,
    "files": [
        {
            "id": "file-1",
            "filename": "modelo_planilha_dl.xlsx",
            "size": 35391,
            "content_type": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        }
    ],
}


def test_build_email_envelope_without_attachment():
    envelope = build_email_envelope(_ITEM_NO_ATTACHMENT, _SOURCE)

    email = envelope["email"]
    assert email["from"] == "ericmaubr@gmail.com"
    assert email["to"] == "glick-tarefa@emailhook.site"
    assert email["subject"] == "teste"
    assert email["body"] == "corpo do e-mail.\r\nbla\r\n"
    assert email["attachments"] == []
    assert email["attachment_names"] == ""


def test_build_email_envelope_falls_back_to_stripped_html_when_no_plain_text():
    item = {**_ITEM_NO_ATTACHMENT, "text_content": None}

    envelope = build_email_envelope(item, _SOURCE)

    assert envelope["email"]["body"] == "corpo do e-mail.bla"


def test_build_email_envelope_downloads_and_embeds_attachment(monkeypatch):
    downloaded_urls = []

    class _FakeResponse:
        content = b"fake xlsx bytes"

        def raise_for_status(self):
            pass

    def fake_get(url, headers=None, timeout=None):
        downloaded_urls.append((url, headers))
        return _FakeResponse()

    monkeypatch.setattr("relaix.email_parsing.requests.get", fake_get)

    envelope = build_email_envelope(_ITEM_WITH_ATTACHMENT, _SOURCE)

    assert downloaded_urls == [
        (
            "https://webhook.site/token/token-abc/request/req-2/download/file-1",
            {"Api-Key": "key-123"},
        )
    ]
    attachment = envelope["email"]["attachments"][0]
    assert attachment["filename"] == "modelo_planilha_dl.xlsx"
    assert base64.b64decode(attachment["content_base64"]) == b"fake xlsx bytes"
    assert envelope["email"]["attachment_names"] == "modelo_planilha_dl.xlsx"
