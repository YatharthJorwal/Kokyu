"""
App-level tests for the unprompted-comment path (Continuous OCR and Task
Guide) with every outside dependency faked: the screen capture, the VLM, the
LLM and TTS. They pin the behavior the real session got wrong -- the model
commenting on an unchanged screen over and over, and those comments piling up
in history until the context window was full.
"""

from __future__ import annotations

import time

import pytest

import ambient
import llm
import tools
import turns
from config import CONFIG
from senses import ocr_watch
from tools import vision


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    ocr_watch.set_active(True)
    spoken: list[str] = []

    async def fake_send_speak(_ws, text):
        spoken.append(text)

    async def fake_log(*_a, **_k):
        return None

    async def fake_stream(_messages, **_kw):
        yield "Look at that mess. [annoyed]"

    monkeypatch.setattr(turns, "send_speak", fake_send_speak)
    monkeypatch.setattr(turns, "log_transcript_turn", fake_log)
    monkeypatch.setattr(llm, "stream_reply", fake_stream)
    monkeypatch.setattr(vision, "capture_screen", lambda *_a, **_k: "b64")
    yield spoken
    ocr_watch.set_active(False)


def _vlm(monkeypatch, summaries):
    """Makes the 'VLM' answer comment_worthy=True with the next summary in
    the list every call -- the over-eager behavior seen in the real log."""
    queue = list(summaries)

    async def fake_check(_prev, _img):
        s = queue.pop(0)
        return {"comment_worthy": True, "summary": s, "note": f"they are looking at {s}"}

    monkeypatch.setattr(ocr_watch, "check_for_comment", fake_check)


@pytest.mark.asyncio
async def test_unchanged_screen_is_not_commented_on_again(monkeypatch, _isolate):
    spoken = _isolate
    _vlm(monkeypatch, [
        "debugging a Python application with an anime avatar",
        "Debugging a Python app with an anime avatar",
        "Debugging a Python app with an anime avatar",
    ])
    ws, history, unprompted = FakeWebSocket(), [{"role": "system", "content": "persona"}], []
    for _ in range(3):
        await ambient.run_ocr_watch_check(ws, history, False, [], unprompted)
    assert len(spoken) == 1  # the first glance only; the two repeats stay quiet


@pytest.mark.asyncio
async def test_a_real_change_still_gets_a_comment_once_the_gap_has_passed(monkeypatch, _isolate):
    spoken = _isolate
    _vlm(monkeypatch, ["player mining wood in Minecraft", "Canva design interface with laptop mockup"])
    ws, history, unprompted = FakeWebSocket(), [{"role": "system", "content": "persona"}], []
    await ambient.run_ocr_watch_check(ws, history, False, [], unprompted)
    # right after speaking, the minimum gap holds the next one back...
    await ambient.run_ocr_watch_check(ws, history, False, [], unprompted)
    assert len(spoken) == 1
    # ...and once it has passed, a genuinely different screen goes through.
    ocr_watch._state = ocr_watch.replace(  # noqa: SLF001
        ocr_watch._state, last_comment_at=ocr_watch._state.last_comment_at - 10_000  # noqa: SLF001
    )
    _vlm(monkeypatch, ["File explorer showing Unity project folders"])
    await ambient.run_ocr_watch_check(ws, history, False, [], unprompted)
    assert len(spoken) == 2


@pytest.mark.asyncio
async def test_typing_that_starts_during_the_check_keeps_her_quiet(monkeypatch, _isolate, caplog):
    # FR-SC-5 (review finding): the check takes seconds; the loop's typing check ran before it.
    spoken = _isolate

    async def typed_meanwhile(_prev, _img):
        monkeypatch.setattr(ambient, "_last_typed_at", time.monotonic())
        return {"comment_worthy": True, "summary": "a spreadsheet", "note": "they are in a spreadsheet"}

    monkeypatch.setattr(ocr_watch, "check_for_comment", typed_meanwhile)
    await ambient.run_ocr_watch_check(FakeWebSocket(), [{"role": "system", "content": "persona"}], False, [], [])
    assert spoken == [] and "the user is typing" in caplog.text


@pytest.mark.asyncio
async def test_suppression_reason_is_logged(monkeypatch, caplog):
    _vlm(monkeypatch, ["Minecraft gameplay with anime avatar overlay"] * 2)
    ws, history = FakeWebSocket(), [{"role": "system", "content": "persona"}]
    await ambient.run_ocr_watch_check(ws, history, False, [], [])
    await ambient.run_ocr_watch_check(ws, history, False, [], [])
    assert "[no comment: same screen as the last check]" in caplog.text


@pytest.mark.asyncio
async def test_history_keeps_only_the_newest_unprompted_comments(monkeypatch):
    # Many different screens, gap forced open each time: history must still
    # hold at most max_unprompted_in_history of them.
    ws, history, flags, unprompted = FakeWebSocket(), [{"role": "system", "content": "persona"}], [], []
    for i in range(12):
        _vlm(monkeypatch, [f"unique screen number{i} topic{i} subject{i} thing{i}"])
        ocr_watch._state = ocr_watch.replace(ocr_watch._state, last_comment_at=0.0)  # noqa: SLF001
        await ambient.run_ocr_watch_check(ws, history, False, flags, unprompted)
    remarks = [m for m in history if m["role"] == "assistant"]
    assert len(remarks) == CONFIG.session.max_unprompted_in_history
    assert len(flags) == len(history) - 1  # temp flags stayed in lockstep


def test_fit_for_llm_leaves_a_short_conversation_alone():
    messages = [{"role": "system", "content": "persona"}, {"role": "user", "content": "hi"}]
    assert turns.fit_for_llm(messages) == messages


def test_fit_for_llm_trims_a_flooded_history_and_says_so(caplog):
    messages = [{"role": "system", "content": "p" * 9000}]
    messages += [{"role": "assistant", "content": "c" * 400} for _ in range(120)]
    messages.append({"role": "user", "content": "what should I do next?"})
    fitted = turns.fit_for_llm(messages, tools.TOOL_SCHEMAS)
    assert fitted[0] is messages[0] and fitted[-1] is messages[-1]
    assert len(fitted) < len(messages)
    assert "left out the" in caplog.text


# --- what she says when the LLM call fails ------------------------------------


def test_each_llm_failure_gets_its_own_line():
    assert turns.llm_failure_line(llm.LLMTimeoutError("slow")) == turns.LLM_TIMEOUT_LINE
    assert turns.llm_failure_line(llm.LLMServerError("500 boom")) == turns.LLM_SERVER_ERROR_LINE
    assert turns.llm_failure_line(llm.LLMUnreachableError("refused")) == turns.LLM_UNREACHABLE_LINE


def test_only_a_real_connection_failure_blames_the_server_not_running():
    # The original bug: a server that was up (and had the model loaded) still
    # got "is the model server even running?".
    assert "Is Ollama running" in turns.LLM_UNREACHABLE_LINE
    assert "running" not in turns.LLM_SERVER_ERROR_LINE
    assert "running" not in turns.LLM_TIMEOUT_LINE


@pytest.mark.asyncio
async def test_a_spoken_remark_is_handed_to_the_chat(monkeypatch, _isolate):
    # Voice off used to mean the remark was lost; now the session stores and shows it.
    _vlm(monkeypatch, ["player mining wood in Minecraft"])
    saved: list[str] = []

    async def on_remark(text):
        saved.append(text)

    await ambient.run_ocr_watch_check(FakeWebSocket(), [{"role": "system", "content": "p"}], False, [], [], on_remark=on_remark)
    assert saved == _isolate and saved


# FR-MODE-9 (review finding): a check takes seconds, and the user may open a roleplay
# (or another thread) meanwhile. The remark belongs to the thread the check started
# in: nothing is streamed from, spoken into, recorded in or stored in the new one.

def _flip_on_stream(monkeypatch, valid):
    async def stream(_messages, **_kw):
        valid["ok"] = False   # the thread changes while the reflex model writes
        yield "Look at that mess. [annoyed]"

    monkeypatch.setattr(llm, "stream_reply", stream)


@pytest.mark.asyncio
async def test_ocr_watch_drops_a_remark_when_the_thread_changes_during_the_check(monkeypatch, _isolate):
    _vlm(monkeypatch, ["a terminal with a failing build"])
    valid, saved = {"ok": True}, []
    _flip_on_stream(monkeypatch, valid)

    async def on_remark(text):
        saved.append(text)

    history, unprompted = [{"role": "system", "content": "p"}], []
    await ambient.run_ocr_watch_check(
        FakeWebSocket(), history, False, [], unprompted, on_remark=on_remark, still_valid=lambda: valid["ok"]
    )
    assert _isolate == [] and saved == [] and unprompted == []
    assert history == [{"role": "system", "content": "p"}]


@pytest.mark.asyncio
async def test_ocr_watch_never_streams_from_a_thread_opened_during_the_vlm_check(monkeypatch, _isolate):
    streamed = []

    async def judged_meanwhile(_prev, _img):
        valid["ok"] = False
        return {"comment_worthy": True, "summary": "a spreadsheet", "note": "they are in a spreadsheet"}

    async def stream(messages, **_kw):
        streamed.append(messages)
        yield "Hm. [neutral]"

    valid = {"ok": True}
    monkeypatch.setattr(ocr_watch, "check_for_comment", judged_meanwhile)
    monkeypatch.setattr(llm, "stream_reply", stream)
    await ambient.run_ocr_watch_check(
        FakeWebSocket(), [{"role": "system", "content": "p"}], False, [], [], still_valid=lambda: valid["ok"]
    )
    assert streamed == [] and _isolate == []


@pytest.mark.asyncio
async def test_task_guide_drops_a_chide_when_the_thread_changes_during_the_check(monkeypatch, _isolate):
    from senses import task_guide

    async def drifted(_desc, _img):
        return {"on_task": False, "note": "a video site"}

    monkeypatch.setattr(task_guide, "check_task_progress", drifted)
    monkeypatch.setattr(task_guide, "mark_checked", lambda: None)
    valid, saved = {"ok": True}, []
    _flip_on_stream(monkeypatch, valid)

    async def on_remark(text):
        saved.append(text)

    history, unprompted = [{"role": "system", "content": "p"}], []
    await ambient.run_task_guide_check(
        FakeWebSocket(), history, "fix the build", False, [], unprompted,
        on_remark=on_remark, still_valid=lambda: valid["ok"],
    )
    assert _isolate == [] and saved == [] and unprompted == []
    assert history == [{"role": "system", "content": "p"}]
