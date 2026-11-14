"""The router: the only way Yuri reaches a model.

Callers ask for a role, never a model. The router decides (pure function), writes
the audit row, checks the budget, and executes -- local unless the decision says
otherwise and the mode allows it.

In `shadow` mode the decision is still computed and logged, but execution is
forced local. That is the default, and it is how the decision rules get exercised
against real traffic before any of them are allowed to cost money.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from functools import partial
from typing import Any, AsyncIterator

import context_budget
from config import CONFIG, Config, ProviderConfig, RoleConfig
from router import decision as decide_mod
from router.audit import AuditWriter
from router.budget import SpendLedger, actual_cost, estimate_cost
from router.decision import decide
from router.discovery import ModelCatalog, repo_path
from router.errors import ProviderError, RouteBlockedError, RouterError, StreamFailed
from router import model_ref as model_refs
from router.providers import AirouterProvider, OllamaNativeProvider
from router.redact import redact_messages
from router.types import (
    INTERNAL,
    SECRET,
    TRUSTED,
    ModelChunk,
    ModelRequest,
    RouteDecision,
    RouterState,
    Usage,
)

__all__ = [
    "Router",
    "ROUTER",
    "ModelChunk",
    "ModelRequest",
    "RouteDecision",
    "RouterState",
    "complete",
    "describe_image",
    "stream_text",
    "stream_with_tools",
    "summarize",
]

_MODEL_FALLBACKS = {"reflex": "qwen3.5:9b"}


BLOCKED_MESSAGES = {
    decide_mod.MODEL_UNSUPPORTED: "This model can't be used yet. Switch to another model.",
    decide_mod.ROLE_PINNED_LOCAL: "Chat is set to local models only in the config. Switch to a local model.",
    decide_mod.PRIVACY_LOCAL_ONLY: "This message has something that must stay on this PC, so it can't go to an API model. Switch to a local model.",
    decide_mod.AMBIENT_CONTEXT: "Screen and camera captures never leave this PC. Switch to a local model for this message.",
    decide_mod.CLOUD_DISABLED: "The API model isn't available: there is no key, or the provider is turned off. Add a key in Settings or switch model.",
    decide_mod.OFFLINE: "The API provider didn't answer a moment ago. Retry, or switch model.",
    decide_mod.BUDGET_EXHAUSTED: "Your spending cap is reached. Raise it in Settings, or switch model.",
    decide_mod.PRICE_UNKNOWN: "The model list has no price for this model, so your spending cap can't be kept. Refresh the list, or switch model.",
}


def blocked_message(reason: str) -> str:
    """What the user is told when their chosen model may not run (FR-R-5)."""
    return BLOCKED_MESSAGES.get(reason, "This model can't answer right now. Retry, or switch model.")


def _default_role(role: str) -> RoleConfig:
    # Unknown role -> local only. Fail safe, not fail open.
    return RoleConfig(chain=("local_ollama",), local_only=True)


class Router:
    def __init__(
        self,
        config: Config = CONFIG,
        *,
        catalog: ModelCatalog | None = None,
        local_provider=None,
        cloud_provider=None,
        llamacpp_provider=None,
        audit: AuditWriter | None = None,
        ledger: SpendLedger | None = None,
        clock=time.time,
    ) -> None:
        self.config = config
        self.clock = clock
        self._started = False
        self._lock = asyncio.Lock()

        cloud_cfg = config.providers.get("airouter")
        self.local_provider = local_provider or OllamaNativeProvider()
        # K1-01 (D-051): built on first use, so a machine without llama.cpp pays nothing.
        self._llamacpp_provider = llamacpp_provider
        self.cloud_provider = cloud_provider
        self._api_key_present = cloud_provider is not None
        if cloud_provider is None and cloud_cfg is not None:
            from config import resolve_api_key

            key = resolve_api_key(cloud_cfg.api_key_env)
            self._api_key_present = bool(key)
            if key:
                self.cloud_provider = AirouterProvider(cloud_cfg, key)

        self.catalog = catalog or ModelCatalog(
            cloud_cfg.base_url if cloud_cfg else "https://api.airouter.in/v1",
            (cloud_cfg.models_cache if cloud_cfg else "data/provider_models.json"),
            ttl_hours=(cloud_cfg.models_refresh_hours if cloud_cfg else 24),
            models_url=(cloud_cfg.models_url if cloud_cfg else None),
        )
        self.audit = audit or AuditWriter(repo_path(config.audit.path))
        self.ledger = ledger or SpendLedger(repo_path(config.budget.ledger_path))
        self.state = RouterState(cloud_available=False)
        # Worst-case cost of AI Router calls still running: the cap counts them
        # before they finish, so calls started together cannot all pass it (FR-R-2).
        self._reserved_usd = 0.0
        self._cloud_cfg: ProviderConfig | None = cloud_cfg
        # None = follow routing.mode/enforce_roles. True/False = the user's live
        # choice from the tray/quick-action toggle, which outranks the config
        # until they change it again (see settings.py).
        self.use_api_model_override: bool | None = None

    def set_use_api_model(self, enabled: bool | None) -> None:
        self.use_api_model_override = enabled

    def _enforce(self, role: str) -> bool:
        """May this role execute a cloud decision right now?"""
        role_cfg = self.config.roles.get(role) or _default_role(role)
        if role_cfg.local_only:
            return False
        if role == decide_mod.CHAT_ROLE:
            # D-025 rule 6: the user's model selection is always enforced; the
            # shadow/enforce rollout and the old API toggle do not apply to chat.
            return True
        if self.use_api_model_override is False:
            return False
        if self.use_api_model_override is True:
            return True
        return (
            self.config.routing.mode == "enforce"
            and role in self.config.routing.enforce_roles
        )

    # -- lifecycle -----------------------------------------------------------

    async def ensure_cloud(self, *, fetch: bool = True) -> bool:
        """Make cloud usable right now if it can be, without a restart.

        A key pasted into `.env` after launch is picked up here, the provider is
        built, and a stale/absent catalog is fetched. Returns whether cloud is
        actually available afterwards. Never raises: a toggle that cannot reach
        the network must still respond with "no key" instead of an exception.
        """
        cloud_cfg = self._cloud_cfg
        if cloud_cfg is None or not cloud_cfg.enabled:
            self.state.cloud_available = False
            return False
        if self.cloud_provider is None:
            from config import resolve_api_key

            key = resolve_api_key(cloud_cfg.api_key_env)
            if key:
                self.cloud_provider = AirouterProvider(cloud_cfg, key)
                self._api_key_present = True
        if self.cloud_provider is None:
            self.state.cloud_available = False
            return False
        try:
            # The cache only fills an empty catalog: it must never replace a fresher list.
            loaded = self.catalog.available or self.catalog.load_cache()
            if fetch and (not loaded or self.catalog.is_stale()):
                await self.catalog.refresh(force=not loaded)
        except Exception as exc:  # noqa: BLE001 -- a toggle must not crash the app
            print(f"[yuri] router: catalog refresh failed: {exc}", flush=True)
        self.state.cloud_available = bool(self.catalog.available and self._api_key_present)
        return self.state.cloud_available

    async def _ensure_started(self) -> None:
        if self._started:
            return
        async with self._lock:
            if self._started:
                return
            await self.startup()
            self._started = True

    async def startup(self) -> bool:
        """Load the catalog and the spend ledger. Returns cloud availability."""
        cloud_cfg = self._cloud_cfg
        cloud_ok = bool(
            cloud_cfg is not None
            and cloud_cfg.enabled
            and self.cloud_provider is not None
            and self._api_key_present
        )
        if cloud_ok:
            loaded = self.catalog.available or self.catalog.load_cache()   # never over a fresher list
            if not loaded or self.catalog.is_stale():
                await self.catalog.refresh(force=not loaded)
            cloud_ok = self.catalog.available
            if not cloud_ok:
                print(
                    "[yuri] router: cloud catalog unavailable -- Mind stays local"
                    + (f" ({self.catalog.last_error})" if self.catalog.last_error else ""),
                    flush=True,
                )
        self.state.cloud_available = cloud_ok
        await self._refresh_spend()
        self._started = True   # app.py calls this directly: the first turn must not run it again
        return cloud_ok

    async def _refresh_spend(self) -> None:
        """The cap checks the ledger as it is now, so a window that has passed
        frees it again (FR-R-2). Off the event loop; a failure keeps the last numbers."""
        try:
            totals = await asyncio.to_thread(self.ledger.totals, self.clock())
        except Exception as exc:  # noqa: BLE001 -- a ledger hiccup must not end a turn
            print(f"[kokyu] router: spend ledger read failed: {exc}", flush=True)
            return
        self.state.spend_hour_usd, self.state.spend_day_usd, self.state.spend_month_usd = totals

    # -- decisions -----------------------------------------------------------

    def _estimate(self, request: ModelRequest) -> int:
        if not request.messages:
            return max(1, sum(len(message.get("content") or "") for message in request.messages) // 4)
        try:
            return context_budget.estimate_prompt(
                [dict(message) for message in request.messages], list(request.tools)
            )
        except Exception:  # noqa: BLE001 -- estimation must never block a turn
            return max(1, sum(len(str(m.get("content") or "")) for m in request.messages) // 4)

    def _anticipated_cloud_cost(
        self, role: str, prompt_tokens: int, max_tokens: int, model_ref: str | None = None
    ) -> tuple[float, bool]:
        """(worst-case cost, whether every cloud model it covers has a price)."""
        if role == decide_mod.CHAT_ROLE:
            try:
                ref = model_refs.parse(model_ref or "")
            except model_refs.ModelRefError:
                return 0.0, True
            if ref.is_local:
                return 0.0, True
            price_in, price_out = self.catalog.price(ref.model)
            return estimate_cost(prompt_tokens, max_tokens, price_in, price_out), self.catalog.priced(ref.model)
        worst, priced = 0.0, True
        role_cfg = self.config.roles.get(role) or _default_role(role)
        for provider in role_cfg.chain:
            if provider == "local_ollama":
                continue
            model = decide_mod.model_for(provider, role, self.config.models)
            price_in, price_out = self.catalog.price(model)
            worst = max(worst, estimate_cost(prompt_tokens, max_tokens, price_in, price_out))
            priced = priced and self.catalog.priced(model)
        return worst, priced

    def _max_tokens(self, request: ModelRequest) -> int:
        """The reply cap an AI Router call is sent with, and the one its worst-case
        estimate assumes: the same number, so the estimate is a bound (FR-R-2).
        A model that may think gets the role's `reasoning_tokens` on top: thinking
        is billed as output and counts against the cap (D-058)."""
        if request.max_tokens:
            return request.max_tokens
        role_cfg = self.config.roles.get(request.role)
        cap = (role_cfg.max_tokens if role_cfg else None) or self.config.llm.max_tokens
        if role_cfg is not None and role_cfg.reasoning_tokens and self._may_reason(request):
            cap += role_cfg.reasoning_tokens
        return cap

    def _may_reason(self, request: ModelRequest) -> bool:
        """An effort was asked for, or the catalog tags a model this request may
        reach (the picked one, else the role's chain) as a reasoner."""
        if model_refs.openai_reasoning_effort(request.effort):
            return True
        try:
            ref = model_refs.parse(request.model_ref or "")
            models = [] if ref.is_local else [ref.model]
        except model_refs.ModelRefError:
            role_cfg = self.config.roles.get(request.role) or _default_role(request.role)
            models = [
                decide_mod.model_for(provider, request.role, self.config.models)
                for provider in role_cfg.chain
                if provider != "local_ollama"
            ]
        for model in models:
            info = self.catalog.info(model)
            if info and {"reasoning", "thinking"} & {str(tag).lower() for tag in info.tags}:
                return True
        return False

    def _effective_privacy(self, request: ModelRequest) -> str:
        for message in request.messages:
            if message.get("images"):
                return SECRET
        return request.privacy_class

    def route(self, request: ModelRequest) -> RouteDecision:
        """Compute (but do not execute) the decision. Public so `--check` and the
        tests can look at it without a provider."""
        role_cfg = self.config.roles.get(request.role) or _default_role(request.role)
        prompt_tokens = self._estimate(request)
        est_cost, priced = self._anticipated_cloud_cost(
            request.role, prompt_tokens, self._max_tokens(request), request.model_ref
        )
        reserved = self._reserved_usd
        state = dataclasses.replace(
            self.state,
            spend_hour_usd=self.state.spend_hour_usd + reserved,
            spend_day_usd=self.state.spend_day_usd + reserved,
            spend_month_usd=self.state.spend_month_usd + reserved,
            est_prompt_tokens=prompt_tokens,
            est_cost_usd=est_cost,
            price_known=priced,
            tool_count=len(request.tools),
        )
        decision = decide(
            role=request.role,
            role_cfg=role_cfg,
            request=dataclasses.replace(request, privacy_class=self._effective_privacy(request)),
            routing=self.config.routing,
            budget=self.config.budget,
            state=state,
            models=self.config.models,
            providers=self.config.providers,
            now=self.clock(),
        )
        if not self._enforce(request.role):
            decision = dataclasses.replace(decision, shadow=True)
        return decision

    def _execution_chain(self, decision: RouteDecision) -> list[str]:
        if decision.shadow or not self._enforce(decision.role):
            # Shadow, or a role we have not opted into: run local, keep the
            # decision as the record of what would have happened.
            local = [c for c in decision.candidates if c.startswith("local_ollama:")]
            return local or [decision.chosen]
        chain = [decision.chosen] + [c for c in decision.candidates if c != decision.chosen]
        return chain

    def _provider(self, name: str):
        if name == "local_ollama":
            return self.local_provider
        if name == "llamacpp":
            if self._llamacpp_provider is None:
                from router.providers.llamacpp import LlamaCppProvider

                self._llamacpp_provider = LlamaCppProvider(self.config.llamacpp)
            return self._llamacpp_provider
        if name == "airouter":
            if self.cloud_provider is None:
                raise RouterError("airouter selected but no provider is configured")
            return self.cloud_provider
        raise RouterError(f"unknown provider {name!r}")

    # -- execution -----------------------------------------------------------

    async def complete(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        await self._ensure_started()
        await self._refresh_spend()
        decision = self.route(request)
        if decision.blocked:
            await asyncio.to_thread(self._audit_blocked, request, decision)
            raise RouteBlockedError(decision.reason, blocked_message(decision.reason), request.model_ref)
        chain = self._execution_chain(decision)
        first = chain[0]
        executed_decision = dataclasses.replace(decision, executed=first)
        redactions: dict[str, int] = {}
        if first.startswith("airouter:"):
            # Counts for the audit row; the actual redacted copy is rebuilt per
            # target below, so a fallback to local still sends the original.
            _, redactions = self._redact_for_cloud(request)

        trace_id: str | None = None
        started = time.monotonic()
        usage: Usage | None = None
        fallback_used = False
        error: str | None = None
        bills: list[tuple[str, float, Usage]] = []   # (model, cost, usage) per AI Router call made
        booked = 0                                    # bills already written to the ledger
        cloud_call: list[Any] | None = None           # [model, usage, characters out, cap] of the one running
        last_kind: str | None = None                  # the last chunk handed to the caller
        interrupted = False                           # stopped, failed or abandoned mid-reply

        reserved = [decision.est_cost_usd if first.startswith("airouter:") else 0.0]
        self._reserved_usd += reserved[0]   # no await since route(): calls started together see each other

        def release() -> None:
            self._reserved_usd -= reserved[0]
            reserved[0] = 0.0
        try:
            trace_id = await self._audit_start(request, executed_decision, redactions)
            for index, target in enumerate(chain):
                provider_name, _, model = target.partition(":")
                if index > 0:
                    fallback_used = True
                produced = False
                try:
                    provider = self._provider(provider_name)
                    outbound = request
                    if provider_name == "airouter":
                        outbound, _ = self._redact_for_cloud(request)
                        outbound = dataclasses.replace(outbound, max_tokens=self._max_tokens(request))
                        cloud_call = [model, None, 0, outbound.max_tokens]
                    async for chunk in provider.complete(outbound, model=model):
                        produced = True
                        if chunk.usage is not None:
                            usage = chunk.usage
                        if cloud_call is not None:
                            if chunk.usage is not None:
                                cloud_call[1] = chunk.usage
                            cloud_call[2] += len(chunk.text) + sum(len(json.dumps(c, default=str)) for c in chunk.calls)
                        last_kind = chunk.kind
                        if chunk.kind == "tool_calls" and cloud_call is not None:
                            # app.py stops reading here and routes the next round at once, long
                            # before this generator is finalized: book the call and free its
                            # reservation now, so the cap sees its real cost (FR-R-2).
                            bills.append(self._bill(cloud_call, decision.est_prompt_tokens))
                            cloud_call = None
                            booked = len(bills)
                            totals = await asyncio.to_thread(self._record, bills[:booked])
                            if totals is not None:
                                self.state.spend_hour_usd, self.state.spend_day_usd, self.state.spend_month_usd = totals
                            release()
                        yield chunk
                    break
                except ProviderError as exc:
                    error = str(exc)
                    if provider_name == "airouter":
                        if not isinstance(exc, StreamFailed):
                            # Refused or unreachable. A stream that failed after HTTP 200 came
                            # from a provider that answered: Retry must still work (FR-R-5).
                            self.state.offline_until = self.clock() + 60.0
                        # Past HTTP 200 (StreamFailed) or after any chunk, the provider may
                        # have billed; refused or unreachable before that, nothing was.
                        if produced or isinstance(exc, StreamFailed):
                            bills.append(self._bill(cloud_call, decision.est_prompt_tokens, interrupted=True))
                        cloud_call = None
                    if index + 1 < len(chain):
                        continue
                    raise
        except BaseException as exc:
            # GeneratorExit right after a tool call (or the end) is the caller done
            # reading, not a failure. Anywhere else the reply was abandoned midway:
            # app.py's Stop usually lands while it awaits between chunks.
            early_close = isinstance(exc, GeneratorExit) and last_kind not in ("tool_calls", "done")
            interrupted = early_close or not isinstance(exc, GeneratorExit)
            if error is None and interrupted:
                if early_close:
                    error = "closed early"
                elif isinstance(exc, asyncio.CancelledError):
                    error = "cancelled"
                else:
                    error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if cloud_call is not None:
                # Finished, stopped, or failed: what was asked for is paid for (FR-R-2).
                bills.append(self._bill(cloud_call, decision.est_prompt_tokens, interrupted=interrupted))
            last = bills[-1][2] if bills else usage
            finish = {
                "role": request.role,
                "latency_ms": (time.monotonic() - started) * 1000.0,
                "prompt_tokens": last.prompt_tokens if last else None,
                "completion_tokens": last.completion_tokens if last else None,
                "cost_usd": sum(cost for _, cost, _ in bills) if bills else None,
                "estimated": any(u.estimated for _, _, u in bills),
                "fallback_used": fallback_used,
                "error": error,
            }
            try:
                totals = await asyncio.to_thread(self._settle, trace_id, bills[booked:], finish)
            finally:
                release()
            if totals is not None:
                self.state.spend_hour_usd, self.state.spend_day_usd, self.state.spend_month_usd = totals

    def _bill(self, call: list[Any], prompt_estimate: int, *, interrupted: bool = False) -> tuple[str, float, Usage]:
        """One AI Router call's cost: the usage the provider reported, else an
        estimate. Prompt: the decision's estimate. Reply: what streamed out, or,
        for a reply cut short, the whole cap: unseen thinking is billed, and many
        providers keep generating after the client hangs up (D-058)."""
        model, reported, characters, cap = call
        prompt = reported.prompt_tokens if reported and reported.prompt_tokens is not None else None
        completion = reported.completion_tokens if reported and reported.completion_tokens is not None else None
        estimated = prompt is None or completion is None or bool(reported and reported.estimated)
        if prompt is None:
            prompt = prompt_estimate
        if completion is None:
            completion = max(cap or 0, -(-characters // 4)) if interrupted else -(-characters // 4)
        price_in, price_out = self.catalog.price(model)
        return model, actual_cost(prompt, completion, price_in, price_out), Usage(prompt, completion, estimated)

    def _settle(
        self, trace_id: str | None, bills: list[tuple[str, float, Usage]], finish: dict[str, Any]
    ) -> tuple[float, float, float] | None:
        """The ledger rows and the audit row of a finished call, in a worker thread.
        Every AI Router call gets a row, $0 included. Neither write may hide the
        reply or the real error: failures are logged (D-058)."""
        totals = self._record(bills)
        if trace_id is not None:
            try:
                self.audit.finish(trace_id, **finish)
            except Exception as exc:  # noqa: BLE001
                print(f"[kokyu] router: audit write failed: {type(exc).__name__}", flush=True)
        return totals

    def _record(self, bills: list[tuple[str, float, Usage]]) -> tuple[float, float, float] | None:
        """Ledger rows for `bills`, then the new totals. Blocking: call it in a thread."""
        totals = None
        try:
            for model, cost, used in bills:
                self.ledger.record(
                    "airouter",
                    model,
                    cost,
                    prompt_tokens=used.prompt_tokens,
                    completion_tokens=used.completion_tokens,
                    estimated=used.estimated,
                    ts=self.clock(),
                )
            if bills:
                totals = self.ledger.totals(self.clock())
        except Exception as exc:  # noqa: BLE001 -- bookkeeping must not kill a reply
            print(f"[kokyu] router: spend ledger write failed: {type(exc).__name__}", flush=True)
        return totals

    async def _audit_start(
        self, request: ModelRequest, decision: RouteDecision, redactions: dict[str, int]
    ) -> str | None:
        """The audit's first row, off the loop. A failed write is logged and the
        call goes ahead (D-058): the audit records calls, it does not gate them."""
        try:
            return await asyncio.to_thread(
                partial(
                    self.audit.start,
                    decision=decision,
                    privacy_class=self._effective_privacy(request),
                    trust=request.trust,
                    redactions=redactions,
                    mode=self.config.routing.mode,
                    job_id=request.job_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[kokyu] router: audit write failed: {type(exc).__name__}", flush=True)
            return None

    def _audit_blocked(self, request: ModelRequest, decision: RouteDecision) -> None:
        try:
            trace_id = self.audit.start(
                decision=decision,
                privacy_class=self._effective_privacy(request),
                trust=request.trust,
                redactions={},
                mode=self.config.routing.mode,
                job_id=request.job_id,
            )
            self.audit.finish(
                trace_id,
                role=request.role,
                latency_ms=0.0,
                prompt_tokens=None,
                completion_tokens=None,
                cost_usd=None,
                estimated=False,
                fallback_used=False,
                error=f"blocked: {decision.reason}",
            )
        except Exception as exc:  # noqa: BLE001 -- the audit must never hide the real error
            print(f"[kokyu] router: audit of a blocked turn failed: {exc}", flush=True)

    async def warm(self, model_ref: str, messages: list[dict], tools: list[dict]) -> None:
        """Loads a chat model and has it read `messages` + `tools` once, so the
        first real turn starts from a cached prefix (K1-01b, D-052). A normal
        `chat` call through the decision path, capped at one token. Raises like
        any call; the caller decides what a failure means."""
        request = ModelRequest(
            role=decide_mod.CHAT_ROLE,
            messages=tuple(messages),
            tools=tuple(tools),
            stream=True,
            max_tokens=1,
            model_ref=model_ref,
        )
        async for _chunk in self.complete(request):
            pass

    @property
    def api_key_present(self) -> bool:
        """Whether the API provider has a key (the picker greys API rows without one)."""
        return self._api_key_present

    async def stop_llamacpp(self) -> bool:
        """Stops llama-server if this router started one; True if one was running.
        Used when the user picks an Ollama chat model: one large local model at a
        time (FR-M-6, D-054)."""
        provider = self._llamacpp_provider
        server = getattr(provider, "server", None)
        if server is None:
            return False
        was_running = bool(server.running())
        await server.stop()
        return was_running

    async def shutdown(self) -> None:
        """Stops child model servers (llama-server) the router started."""
        await self.stop_llamacpp()

    def _redact_for_cloud(self, request: ModelRequest) -> tuple[ModelRequest, dict[str, int]]:
        if any(message.get("images") for message in request.messages):
            raise RouterError("refusing to send images to a cloud provider")
        settings = dict(self.config.privacy.redaction)
        messages, counts = redact_messages([dict(m) for m in request.messages], settings)
        return dataclasses.replace(request, messages=tuple(messages)), counts

    # -- convenience, shaped like llm.py so callers barely change ------------

    async def stream_text(
        self,
        role: str,
        messages: list[dict],
        *,
        privacy_class: str = INTERNAL,
        trust: str = TRUSTED,
        background: bool = False,
        explicit_escalation: bool = False,
        job_id: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        request = ModelRequest(
            role=role,
            messages=tuple(messages),
            stream=True,
            privacy_class=privacy_class,
            trust=trust,
            background=background,
            explicit_escalation=explicit_escalation,
            job_id=job_id,
            **kwargs,
        )
        async for chunk in self.complete(request):
            if chunk.kind == "content":
                yield chunk.text

    async def stream_with_tools(
        self,
        role: str,
        messages: list[dict],
        tools: list[dict],
        *,
        privacy_class: str = INTERNAL,
        trust: str = TRUSTED,
        **kwargs,
    ) -> AsyncIterator[dict]:
        request = ModelRequest(
            role=role,
            messages=tuple(messages),
            tools=tuple(tools),
            stream=True,
            privacy_class=privacy_class,
            trust=trust,
            **kwargs,
        )
        async for chunk in self.complete(request):
            if chunk.kind == "content":
                yield {"type": "content", "text": chunk.text}
            elif chunk.kind == "tool_calls":
                yield {"type": "tool_calls", "calls": list(chunk.calls)}

    async def describe_image(
        self,
        role: str,
        prompt: str,
        image_b64: str,
        json_schema: dict | None = None,
    ) -> str:
        """Vision always runs local: pixels are `secret` and rule 2 fires."""
        request = ModelRequest(
            role=role,
            messages=({"role": "user", "content": prompt, "images": [image_b64]},),
            privacy_class=SECRET,
            stream=False,
        )
        await self._ensure_started()
        decision = self.route(request)
        model = decide_mod.model_for("local_ollama", role, self.config.models)
        trace_id = self.audit.start(
            decision=dataclasses.replace(decision, executed="local_ollama:" + model),
            privacy_class=SECRET,
            trust=TRUSTED,
            mode=self.config.routing.mode,
        )
        started = time.monotonic()
        error = None
        try:
            return await self.local_provider.describe_image(
                prompt, image_b64, model=model, json_schema=json_schema
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.audit.finish(
                trace_id,
                role=role,
                latency_ms=(time.monotonic() - started) * 1000.0,
                error=error,
            )


# -- module-level singleton + functions ---------------------------------------
# Importing this module must not hit the network; Router.startup() is called on
# the first complete()/describe_image(), i.e. from the app's own lifespan.

_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router()
    return _router


async def complete(request: ModelRequest) -> AsyncIterator[ModelChunk]:
    async for chunk in get_router().complete(request):
        yield chunk


async def stream_text(role: str, messages: list[dict], **kwargs) -> AsyncIterator[str]:
    async for text in get_router().stream_text(role, messages, **kwargs):
        yield text


async def stream_with_tools(role: str, messages: list[dict], tools: list[dict], **kwargs) -> AsyncIterator[dict]:
    async for event in get_router().stream_with_tools(role, messages, tools, **kwargs):
        yield event


async def describe_image(role: str, prompt: str, image_b64: str, json_schema: dict | None = None) -> str:
    return await get_router().describe_image(role, prompt, image_b64, json_schema)


def summarize(router: Router | None = None) -> str:
    """Human-readable status, for `check.py` and the startup log."""
    r = router or get_router()
    lines = [f"mode: {r.config.routing.mode} (enforce roles: {', '.join(r.config.routing.enforce_roles) or '-'})"]
    lines.append(
        f"cloud: {'available' if r.state.cloud_available else 'unavailable'}"
        f"  catalog: {len(r.catalog.model_ids())} models"
        + (f"  last error: {r.catalog.last_error}" if r.catalog.last_error else "")
    )
    hour, day, month = r.ledger.totals()
    lines.append(
        f"spend: hour ${hour:.4f}/{r.config.budget.hourly_usd}  "
        f"day ${day:.4f}/{r.config.budget.daily_usd}  "
        f"month ${month:.4f}/{r.config.budget.monthly_usd}"
    )
    for name, role in r.config.roles.items():
        print_chain = " -> ".join(
            decide_mod.model_for(provider, name, r.config.models) if provider == "local_ollama"
            else f"{provider}:{decide_mod.model_for(provider, name, r.config.models)}"
            for provider in role.chain
        )
        lines.append(f"  {name:<14} {'local-only' if role.local_only else 'escalatable':<11} {print_chain}")
    return "\n".join(lines)
