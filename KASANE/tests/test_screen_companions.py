"""K1-05b (FR-SC-1..4, D-048): Task Guide and OCR watch are opt-in, refuse to
start without a local vision model, and every window sees what is watching."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import app
from senses import ocr_watch, task_guide


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(app, "_conversation_manager", None)
    monkeypatch.setattr(app, "_driver", None)
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())
    caps = {"value": ["completion", "vision"]}

    async def capabilities(model):
        return caps["value"]

    monkeypatch.setattr(app.llm, "model_capabilities", capabilities)
    task_guide.set_enabled(False)
    ocr_watch.set_active(False)
    yield TestClient(app.app), caps
    task_guide.set_enabled(False)
    ocr_watch.set_active(False)


def _until(ws, kind):
    while True:
        msg = ws.receive_json()
        if msg.get("type") == kind:
            return msg


def _switch(ws, **data):
    ws.send_json({"v": 1, "type": "screen_companion", "data": data})


def test_both_start_off_and_the_tray_turns_them_on_and_off(kernel):
    client, _ = kernel
    with client.websocket_connect("/ws") as ws:
        first = _until(ws, "screen_companions")["data"]
        assert first == {"task_guide": {"on": False, "task": None}, "ocr_watch": {"on": False}}
        _switch(ws, mode="task_guide", on=True, task="write the essay intro")
        assert _until(ws, "screen_companions")["data"]["task_guide"] == {"on": True, "task": "write the essay intro"}
        _switch(ws, mode="task_guide", on=True, task="fix the login bug")          # replacing is one action
        assert _until(ws, "screen_companions")["data"]["task_guide"]["task"] == "fix the login bug"
        _switch(ws, mode="ocr_watch", on=True)
        assert _until(ws, "screen_companions")["data"]["ocr_watch"] == {"on": True}
        _switch(ws, mode="task_guide", on=False)                                    # one click stops it
        data = _until(ws, "screen_companions")["data"]
    assert data["task_guide"] == {"on": False, "task": None} and data["ocr_watch"]["on"] is True
    assert task_guide.get_state().active is False


@pytest.mark.parametrize(("caps", "says"), [(None, "Is Ollama running"), (["completion"], "cannot")])
def test_without_a_local_vision_model_they_refuse_to_start(kernel, caps, says):
    client, holder = kernel
    holder["value"] = caps
    with client.websocket_connect("/ws") as ws:
        _until(ws, "screen_companions")
        _switch(ws, mode="ocr_watch", on=True)
        err = _until(ws, "error")
        assert err["data"]["code"] == "vision_unavailable" and says in err["data"]["message"]
        assert _until(ws, "screen_companions")["data"]["ocr_watch"]["on"] is False
    assert ocr_watch.get_state().active is False


def test_an_observer_window_cannot_switch_them(kernel, monkeypatch):
    client, _ = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "screen_companions")
        monkeypatch.setattr(app, "_driver", object())   # this window is now an observer
        _switch(ws, mode="ocr_watch", on=True)
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert ocr_watch.get_state().active is False


def test_the_widgets_old_ocr_toggle_gets_the_same_gate_and_vision_check(kernel, monkeypatch):
    # Review finding: Yuri's widget still sends set_ocr_watch.
    client, holder = kernel
    holder["value"] = ["completion"]
    with client.websocket_connect("/ws") as ws:
        _until(ws, "screen_companions")
        ws.send_json({"type": "set_ocr_watch", "enabled": True})
        assert _until(ws, "error")["data"]["code"] == "vision_unavailable"
        holder["value"] = ["completion", "vision"]
        monkeypatch.setattr(app, "_driver", object())   # an observer window
        ws.send_json({"type": "set_ocr_watch", "enabled": True})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert ocr_watch.get_state().active is False


def test_typing_keeps_ocr_watch_quiet_for_a_while(kernel, monkeypatch):
    # FR-SC-5: no remark while the user is typing.
    client, _ = kernel
    monkeypatch.setattr(app, "_last_typed_at", 0.0)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "screen_companions")
        ws.send_json({"v": 1, "type": "typing", "data": {}})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    typed = app._last_typed_at
    assert typed > 0 and app._typing_recently(typed + 1)
    assert not app._typing_recently(typed + app.TYPING_QUIET_SECONDS + 0.1)
