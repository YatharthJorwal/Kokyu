"""K1-08 (FR-R-2, FR-R-6): every AI Router call is billed and audited truthfully
-- tool rounds, Stop, failures, missing usage -- and the cap holds."""

import asyncio
import contextlib
import dataclasses
import json
import sqlite3

import pytest

import config
from router import Router
from router import decision as d
from router.audit import AuditWriter
from router.budget import SpendLedger
from router.errors import ProviderError, RouteBlockedError, StreamFailed
from router.types import ModelChunk, ModelRequest, Usage

from test_router import FakeCatalog, FakeProvider, audit_rows, drain, make_config

API = "api:airouter/deepseek/deepseek-v4-flash"


class Scripted:
    """A cloud provider that streams the given chunks (an exception is raised
    where it stands) and keeps every request it got."""

    name = "airouter"

    def __init__(self, *script, pause=0.0):
        self.script = script
        self.pause = pause
        self.requests = []

    async def complete(self, request, *, model):
        self.requests.append(request)
        for item in self.script:
            if self.pause:
                await asyncio.sleep(self.pause)
            if isinstance(item, BaseException):
                raise item
            yield item


def router_with(tmp_path, cloud, *, catalog=None, clock=None, audit=None, **budget):
    cfg = make_config(tmp_path, mode="enforce")
    cfg = dataclasses.replace(cfg, budget=dataclasses.replace(cfg.budget, enabled=True, **budget))
    return Router(
        cfg,
        catalog=catalog or FakeCatalog(),
        local_provider=FakeProvider("local_ollama"),
        cloud_provider=cloud,
        audit=audit or AuditWriter(tmp_path / "audit.jsonl"),
        ledger=SpendLedger(tmp_path / "spend.db"),
        **({"clock": clock} if clock else {}),
    )


def ask():
    return ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), model_ref=API)


def ledger_rows(tmp_path):
    with sqlite3.connect(tmp_path / "spend.db") as conn:
        return conn.execute("SELECT cost_usd, prompt_tokens, completion_tokens, estimated FROM spend").fetchall()


def finished(tmp_path):
    return [r for r in audit_rows(tmp_path) if r["event"] == "model.call.finished"]


@pytest.mark.asyncio
async def test_a_tool_round_is_billed_though_the_caller_stops_at_the_tool_call(tmp_path):
    used = Usage(prompt_tokens=1000, completion_tokens=50)
    cloud = Scripted(ModelChunk(kind="usage", usage=used), ModelChunk.tool_calls([{"name": "x", "arguments": {}}]), ModelChunk.done(used))
    router = router_with(tmp_path, cloud)
    stream = router.complete(ask())
    async for chunk in stream:
        if chunk.kind == "tool_calls":
            break                                           # what turns.py does
    await stream.aclose()
    assert ledger_rows(tmp_path) == [(pytest.approx((1000 * 0.5 + 50 * 1.5) / 1e6), 1000, 50, 0)]
    assert finished(tmp_path)[0]["error"] is None           # putting the stream down is not a failure


@pytest.mark.asyncio
async def test_stop_mid_reply_is_billed_up_to_its_cap_and_audited_as_cancelled(tmp_path):
    cloud = Scripted(ModelChunk.content("Hello there"), ModelChunk.content(" and more"), ModelChunk.done(Usage(9, 9)), pause=0.05)
    router = router_with(tmp_path, cloud)
    task = asyncio.create_task(drain(router, ask()))
    await asyncio.sleep(0.08)                               # after the first chunk
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    (cost, prompt, completion, estimated), = ledger_rows(tmp_path)
    # Unseen thinking is billed, and the provider may keep going after the hang-up.
    assert cost > 0 and prompt > 0 and completion == router._max_tokens(ask()) and estimated == 1
    assert finished(tmp_path)[0]["error"] == "cancelled" and finished(tmp_path)[0]["estimated"] is True
    assert router._reserved_usd == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_a_reply_without_usage_is_billed_by_estimate(tmp_path):
    router = router_with(tmp_path, Scripted(ModelChunk.content("x" * 40), ModelChunk.done(None)))
    await drain(router, ask())
    (cost, _, completion, estimated), = ledger_rows(tmp_path)
    assert cost > 0 and completion == 10 and estimated == 1


@pytest.mark.asyncio
async def test_a_refused_call_costs_nothing_but_a_broken_one_mid_reply_is_billed(tmp_path):
    router = router_with(tmp_path, Scripted(ProviderError("401 from the provider")))
    with pytest.raises(ProviderError):
        await drain(router, ask())
    assert ledger_rows(tmp_path) == []
    assert "401" in finished(tmp_path)[0]["error"]

    router = router_with(tmp_path, Scripted(ModelChunk.content("half a rep"), ProviderError("the reply stream was cut off")))
    with pytest.raises(ProviderError):
        await drain(router, ask())
    assert len(ledger_rows(tmp_path)) == 1 and ledger_rows(tmp_path)[0][3] == 1


@pytest.mark.asyncio
async def test_the_cap_frees_up_once_its_window_has_passed(tmp_path):
    now = {"t": 1_000_000.0}
    router = router_with(tmp_path, Scripted(ModelChunk.content("ok"), ModelChunk.done(Usage(5, 1))),
                         clock=lambda: now["t"], hourly_usd=0.003, daily_usd=-1.0, monthly_usd=-1.0)
    router.ledger.record("airouter", "m", 0.002, ts=now["t"])   # one call's worst case (~$0.0018) does not fit
    with pytest.raises(RouteBlockedError) as blocked:
        await drain(router, ask())
    assert blocked.value.reason == d.BUDGET_EXHAUSTED
    now["t"] += 2 * 3600
    await drain(router, ask())                                  # used to stay blocked until a restart


@pytest.mark.asyncio
async def test_an_api_call_is_sent_with_the_reply_cap_its_estimate_assumes(tmp_path):
    cloud = Scripted(ModelChunk.done(Usage(1, 1)))
    await drain(router_with(tmp_path, cloud), ask())
    assert cloud.requests[0].max_tokens == config.CONFIG.roles["chat"].max_tokens


@pytest.mark.asyncio
async def test_calls_started_together_cannot_all_pass_the_cap(tmp_path):
    cloud = Scripted(ModelChunk.content("ok"), ModelChunk.done(Usage(5, 1)), pause=0.05)
    router = router_with(tmp_path, cloud, hourly_usd=0.003, daily_usd=-1.0, monthly_usd=-1.0)
    results = await asyncio.gather(drain(router, ask()), drain(router, ask()), return_exceptions=True)
    assert sum(isinstance(r, RouteBlockedError) for r in results) == 1 and len(cloud.requests) == 1
    assert router._reserved_usd == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_a_model_without_a_price_is_refused_while_a_cap_is_on(tmp_path):
    class Unpriced(FakeCatalog):
        def priced(self, model):
            return False

    cloud = Scripted(ModelChunk.done(Usage(1, 1)))
    with pytest.raises(RouteBlockedError) as blocked:
        await drain(router_with(tmp_path, cloud, catalog=Unpriced()), ask())
    assert blocked.value.reason == d.PRICE_UNKNOWN and "price" in blocked.value.message
    router = router_with(tmp_path, cloud, catalog=Unpriced(), hourly_usd=-1.0, daily_usd=-1.0, monthly_usd=-1.0)
    await drain(router, ask())                                  # no cap to keep: it runs, and is recorded
    assert len(cloud.requests) == 1 and len(ledger_rows(tmp_path)) == 1


@pytest.mark.asyncio
async def test_an_unexpected_failure_is_audited_and_a_broken_audit_hides_nothing(tmp_path):
    router = router_with(tmp_path, Scripted(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        await drain(router, ask())
    assert finished(tmp_path)[0]["error"] == "RuntimeError: boom"

    class Broken(AuditWriter):
        def start(self, **_k):
            raise OSError("audit.jsonl is locked")

        def finish(self, *_a, **_k):
            raise OSError("audit.jsonl is locked")

    router = router_with(tmp_path, Scripted(ModelChunk.content("still here"), ModelChunk.done(Usage(1, 1))),
                         audit=Broken(tmp_path / "other.jsonl"))
    chunks = await drain(router, ask())
    assert "".join(c.text for c in chunks) == "still here"


def test_the_audit_never_keeps_a_secret_in_an_error(tmp_path):
    audit = AuditWriter(tmp_path / "audit.jsonl")
    audit.finish("t1", role="chat", latency_ms=1.0, error="401: bad key sk-abcdefghijklmnopqrstuvwxyz")
    row = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert "sk-abc" not in row["error"] and "[secret]" in row["error"]


@pytest.mark.asyncio
async def test_a_stream_that_fails_after_it_was_accepted_is_billed_though_nothing_showed(tmp_path):
    # A reasoning model can think for minutes and then drop: no chunk, but a bill.
    router = router_with(tmp_path, Scripted(StreamFailed("the reply stream was cut off")))
    with pytest.raises(StreamFailed):
        await drain(router, ask())
    (_, _, completion, estimated), = ledger_rows(tmp_path)
    assert completion == router._max_tokens(ask()) and estimated == 1


@pytest.mark.asyncio
async def test_a_reply_put_down_midway_is_billed_and_audited_as_closed_early(tmp_path):
    router = router_with(tmp_path, Scripted(ModelChunk.content("Hel"), ModelChunk.content("lo"), ModelChunk.done(None)))
    stream = router.complete(ask())
    async for chunk in stream:
        break                                                   # not at a tool call: abandoned
    await stream.aclose()
    (_, _, completion, _), = ledger_rows(tmp_path)
    assert completion == router._max_tokens(ask())
    assert finished(tmp_path)[0]["error"] == "closed early"


@pytest.mark.asyncio
async def test_a_model_that_may_think_gets_room_to_think_in_its_cap(tmp_path):
    class Reasoner(FakeCatalog):
        def info(self, model):
            return dataclasses.make_dataclass("Info", [("tags", tuple)])(("Reasoning",))

    role = config.CONFIG.roles["chat"]
    plain, by_effort, by_tag = Scripted(ModelChunk.done(Usage(1, 1))), Scripted(ModelChunk.done(Usage(1, 1))), Scripted(ModelChunk.done(Usage(1, 1)))
    await drain(router_with(tmp_path, plain), ask())
    await drain(router_with(tmp_path, by_effort), dataclasses.replace(ask(), effort="high"))
    await drain(router_with(tmp_path, by_tag, catalog=Reasoner()), ask())
    assert role.reasoning_tokens
    assert plain.requests[0].max_tokens == role.max_tokens
    assert by_effort.requests[0].max_tokens == by_tag.requests[0].max_tokens == role.max_tokens + role.reasoning_tokens


@pytest.mark.asyncio
async def test_a_fresh_model_list_is_never_replaced_by_the_cache(tmp_path):
    class Counting(FakeCatalog):
        def __init__(self, available):
            self.available, self.loads, self.fetches = available, 0, 0

        def load_cache(self):
            self.loads += 1
            return True

        async def refresh(self, *, force=False):
            self.fetches += 1
            return True

    fresh = Counting(available=True)
    await router_with(tmp_path, Scripted(), catalog=fresh).ensure_cloud(fetch=False)
    assert (fresh.loads, fresh.fetches) == (0, 0)               # the list that just came back stands
    empty = Counting(available=False)
    await router_with(tmp_path, Scripted(), catalog=empty).ensure_cloud(fetch=False)
    assert (empty.loads, empty.fetches) == (1, 0)


@pytest.mark.asyncio
async def test_a_tool_round_frees_its_reservation_before_the_next_round_is_routed(tmp_path):
    # turns.py breaks out at the tool call and asks again at once; the stream is only
    # finalized later. The next round must see this call's real cost, not its worst case.
    used = Usage(prompt_tokens=1000, completion_tokens=50)
    cloud = Scripted(ModelChunk(kind="usage", usage=used), ModelChunk.tool_calls([{"name": "x", "arguments": {}}]), ModelChunk.done(used))
    router = router_with(tmp_path, cloud, hourly_usd=0.003, daily_usd=-1.0, monthly_usd=-1.0)
    messages = [{"role": "user", "content": "hi"}]
    async for event in router.stream_with_tools("chat", messages, [{"name": "x"}], model_ref=API):
        if event["type"] == "tool_calls":
            break                                               # no aclose: what turns.py does
    assert router._reserved_usd == pytest.approx(0.0) and len(ledger_rows(tmp_path)) == 1
    await drain(router, ask())                                  # worst case 0.0018 + real 0.000575 fits 0.003
    assert len(cloud.requests) == 2 and len(ledger_rows(tmp_path)) == 2


@pytest.mark.asyncio
async def test_a_provider_that_answered_and_then_failed_is_not_marked_offline(tmp_path):
    now = {"t": 1_000.0}
    router = router_with(tmp_path, Scripted(StreamFailed("the model used its whole reply cap")), clock=lambda: now["t"])
    with pytest.raises(StreamFailed):
        await drain(router, ask())
    assert router.state.offline_until <= now["t"]               # Retry (with lower effort) goes through
    router = router_with(tmp_path, Scripted(ProviderError("couldn't reach the provider")), clock=lambda: now["t"])
    with pytest.raises(ProviderError):
        await drain(router, ask())
    assert router.state.offline_until > now["t"]                # unreachable: the short back-off stays


@pytest.mark.asyncio
async def test_a_failure_that_reported_usage_is_billed_by_that_usage(tmp_path):
    cloud = Scripted(ModelChunk(kind="usage", usage=Usage(5, 7200)), StreamFailed("the model used its whole reply cap"))
    router = router_with(tmp_path, cloud)
    with pytest.raises(StreamFailed):
        await drain(router, ask())
    assert ledger_rows(tmp_path) == [(pytest.approx((5 * 0.5 + 7200 * 1.5) / 1e6), 5, 7200, 0)]


@pytest.mark.asyncio
async def test_startup_keeps_a_fresher_model_list_and_runs_once(tmp_path):
    class Counting(FakeCatalog):
        loads = 0

        def load_cache(self):
            self.loads += 1
            return True

    catalog = Counting()
    router = router_with(tmp_path, Scripted(ModelChunk.done(Usage(1, 1))), catalog=catalog)
    await router.startup()                                      # what app.py's lifespan does
    await drain(router, ask())                                  # must not run startup() again
    assert catalog.loads == 0


@pytest.mark.asyncio
async def test_the_chat_stream_hands_on_real_token_counts_only(tmp_path):
    # FR-C-10: the stored reply records the counts the provider reported; an estimate is not one.
    real = Usage(prompt_tokens=1000, completion_tokens=50)
    router = router_with(tmp_path, Scripted(ModelChunk.content("hi"), ModelChunk(kind="usage", usage=real), ModelChunk.done(real)))
    messages = [{"role": "user", "content": "hi"}]
    events = [e async for e in router.stream_with_tools("chat", messages, [], model_ref=API)]
    assert events == [{"type": "content", "text": "hi"}, {"type": "usage", "tokens_in": 1000, "tokens_out": 50}]

    guess = Usage(prompt_tokens=10, completion_tokens=5, estimated=True)
    router = router_with(tmp_path, Scripted(ModelChunk.content("hi"), ModelChunk(kind="usage", usage=guess)))
    events = [e async for e in router.stream_with_tools("chat", messages, [], model_ref=API)]
    assert events == [{"type": "content", "text": "hi"}]
