import asyncio
from typing import Any

import pytest

from astrbot.core.platform.sources.weixin_oc.weixin_oc_adapter import WeixinOCAdapter


class FakeWeixinOCClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request_json(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        token_required: bool = False,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "method": method,
                "endpoint": endpoint,
                "payload": payload,
                "token_required": token_required,
                "headers": headers,
            }
        )
        return self.responses.pop(0)


def make_adapter(
    responses: list[dict[str, Any]],
) -> tuple[WeixinOCAdapter, FakeWeixinOCClient]:
    adapter = WeixinOCAdapter(
        {
            "id": "weixin_oc_test",
            "type": "weixin_oc",
            "weixin_oc_token": "token",
            "weixin_oc_context_tokens": {"user": "context-token"},
        },
        {},
        asyncio.Queue(),
    )
    client = FakeWeixinOCClient(responses)
    adapter.client = client
    return adapter, client


@pytest.mark.asyncio
async def test_sendmessage_succeeds_without_retry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(WeixinOCAdapter, "SENDMESSAGE_RETRY_DELAYS_S", (0.0,))
    adapter, client = make_adapter([{"ret": 0, "errcode": 0}])

    sent = await adapter._send_items_to_session(
        "user",
        [{"type": 1, "text_item": {"text": "course reminder"}}],
    )

    assert sent is True
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_sendmessage_retries_ret_minus_two_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(WeixinOCAdapter, "SENDMESSAGE_RETRY_DELAYS_S", (0.0,))
    adapter, client = make_adapter(
        [
            {"ret": -2, "errcode": 0, "errmsg": ""},
            {"ret": 0, "errcode": 0},
        ]
    )

    sent = await adapter._send_items_to_session(
        "user",
        [{"type": 1, "text_item": {"text": "course reminder"}}],
    )

    assert sent is True
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_sendmessage_returns_false_after_retryable_failures(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(WeixinOCAdapter, "SENDMESSAGE_RETRY_DELAYS_S", (0.0, 0.0))
    adapter, client = make_adapter(
        [
            {"ret": -2, "errcode": 0, "errmsg": ""},
            {"ret": -2, "errcode": 0, "errmsg": ""},
            {"ret": -2, "errcode": 0, "errmsg": ""},
        ]
    )

    sent = await adapter._send_items_to_session(
        "user",
        [{"type": 1, "text_item": {"text": "course reminder"}}],
    )

    assert sent is False
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_sendmessage_does_not_retry_non_retryable_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(WeixinOCAdapter, "SENDMESSAGE_RETRY_DELAYS_S", (0.0,))
    adapter, client = make_adapter(
        [{"ret": 0, "errcode": 40001, "errmsg": "bad token"}]
    )

    sent = await adapter._send_items_to_session(
        "user",
        [{"type": 1, "text_item": {"text": "course reminder"}}],
    )

    assert sent is False
    assert len(client.calls) == 1
