"""K1-09: the VRAM reader, measured cache, estimates and the fits hint."""
from __future__ import annotations

import subprocess

import pytest

import vram


def test_nvidia_smi_output_is_parsed():
    gpu = vram.parse_smi("NVIDIA GeForce RTX 3060, 12288, 11726, 388\n")
    assert gpu == vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 11726, 388)
    assert vram.parse_smi("") is None
    assert vram.parse_smi("garbage\nNVIDIA X, [N/A], 1, 2") is None
    # two cards: which one a backend uses is unknown, so the reading is too
    assert vram.parse_smi("NVIDIA GeForce GT 1030, 2048, 300, 1748\nNVIDIA GeForce RTX 3060, 12288, 900, 11388\n") is None


def test_smi_reader_handles_a_missing_or_failing_tool(monkeypatch):
    monkeypatch.setattr(vram, "_smi_path", lambda: None)
    assert vram._read_smi() is None                       # no NVIDIA driver: unknown, no crash

    monkeypatch.setattr(vram, "_smi_path", lambda: r"C:\Windows\System32\nvidia-smi.exe")

    def ok(cmd, **kw):
        assert kw["timeout"] == 5
        return subprocess.CompletedProcess(cmd, 0, stdout="GPU, 8192, 1000, 7192\n", stderr="")

    assert vram._read_smi(run=ok) == vram.GpuMemory("GPU", 8192, 1000, 7192)

    def broken(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 5)

    assert vram._read_smi(run=broken) is None
    assert vram._read_smi(run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 9, stdout="", stderr="")) is None


def test_measured_values_survive_a_restart_and_bad_files_are_ignored(tmp_path):
    path = tmp_path / "vram_measured.json"
    cache = vram.MeasuredCache(path)
    assert cache.get("local:ollama/qwen3.5:9b") is None
    cache.record("local:ollama/qwen3.5:9b", 7300)
    cache.record("local:ollama/zero", 0)                  # nonsense is not stored
    assert vram.MeasuredCache(path).get("local:ollama/qwen3.5:9b") == 7300
    assert vram.MeasuredCache(path).get("local:ollama/zero") is None
    path.write_text("{not json", encoding="utf-8")
    assert vram.MeasuredCache(path).get("local:ollama/qwen3.5:9b") is None


def test_estimates_prefer_override_then_measurement_then_file_size():
    common = dict(ctx=8192, kv_mb_per_1k_ctx=96, margin_mb=512)
    assert vram.estimate_mb(measured=None, file_bytes=6_600 * vram.MB, **common) == 6600 + 768 + 512
    assert vram.estimate_mb(measured=7300, file_bytes=6_600 * vram.MB, **common) == 7300
    assert vram.estimate_mb(measured=7300, file_bytes=None, override_mb=3000, **common) == 3000
    # a MoE with its experts in RAM: the 21 GB file says nothing about VRAM
    assert vram.estimate_mb(measured=None, file_bytes=21_000 * vram.MB, experts_on_cpu=True, **common) is None
    assert vram.estimate_mb(measured=None, file_bytes=None, **common) is None


def test_fits_counts_what_the_current_model_frees():
    gpu = vram.GpuMemory("GPU", 12288, 11726, 562)         # 9B + 4B + embeddings loaded
    assert vram.fits(7000, gpu) is False
    assert vram.fits(7000, gpu, freed_mb=7300) is True     # swapping the 9B for another 7 GB model
    assert vram.fits(12000, gpu, freed_mb=7300) is False
    assert vram.fits(None, gpu) is None and vram.fits(1000, None) is None


# -- NVML through ctypes, with a fake driver library ------------------------------


class FakeNvml:
    """Stands in for nvml.dll: fills the out-parameters the way the driver does."""

    def __init__(self, *, init=0, handle=0, memory=0, name=0, gpus=1):
        self.codes = dict(init=init, handle=handle, memory=memory, name=name)
        self.gpus = gpus
        self.shutdowns = 0

    def nvmlInit_v2(self):
        return self.codes["init"]

    def nvmlDeviceGetCount_v2(self, count):
        count._obj.value = self.gpus
        return 0

    def nvmlDeviceGetHandleByIndex_v2(self, index, handle):
        handle._obj.value = 1234
        return self.codes["handle"]

    def nvmlDeviceGetMemoryInfo(self, handle, memory):
        mem = memory._obj
        mem.total, mem.free, mem.used = 12288 * vram.MB, 9000 * vram.MB, 3288 * vram.MB
        return self.codes["memory"]

    def nvmlDeviceGetName(self, handle, buffer, length):
        buffer.value = b"NVIDIA GeForce RTX 3060"
        return self.codes["name"]

    def nvmlShutdown(self):
        self.shutdowns += 1
        return 0


def test_nvml_is_read_from_the_driver_library_and_always_shut_down():
    lib = FakeNvml()
    assert vram._read_nvml(load=lambda: lib) == vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 3288, 9000)
    assert lib.shutdowns == 1

    no_name = FakeNvml(name=1)
    assert vram._read_nvml(load=lambda: no_name).name == "NVIDIA GPU"   # the memory is what matters

    failing = FakeNvml(memory=999)
    assert vram._read_nvml(load=lambda: failing) is None and failing.shutdowns == 1

    no_init = FakeNvml(init=9)
    assert vram._read_nvml(load=lambda: no_init) is None and no_init.shutdowns == 0

    two_cards = FakeNvml(gpus=2)                                  # index 0 may not be the one in use
    assert vram._read_nvml(load=lambda: two_cards) is None and two_cards.shutdowns == 1
    assert vram._read_nvml(load=lambda: FakeNvml(gpus=0)) is None


def test_no_driver_library_means_unknown_and_falls_back_to_nvidia_smi(monkeypatch):
    def unloadable():
        raise OSError("not a valid Win32 application")

    assert vram._read_nvml(load=lambda: None) is None
    assert vram._read_nvml(load=unloadable) is None
    smi = vram.GpuMemory("GPU", 8192, 1000, 7192)
    monkeypatch.setattr(vram, "_read_nvml", lambda: None)
    monkeypatch.setattr(vram, "_read_smi", lambda: smi)
    assert vram.read_gpu() == smi


def test_only_full_paths_are_tried_for_the_driver_library(monkeypatch):
    monkeypatch.setattr(vram.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    found = vram._nvml_candidates()
    assert found and all(p.is_absolute() and p.name == "nvml.dll" for p in found)


def test_an_nvidia_smi_planted_in_the_working_folder_is_never_run(tmp_path, monkeypatch):
    monkeypatch.setattr(vram.sys, "platform", "win32")
    windows, planted = tmp_path / "Windows", tmp_path / "cwd"
    planted.mkdir()
    (planted / "nvidia-smi.exe").write_bytes(b"")
    (planted / "nvidia-smi.bat").write_text("@echo Planted GPU, 99999, 1, 99998", encoding="utf-8")
    monkeypatch.setenv("SystemRoot", str(windows))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    monkeypatch.chdir(planted)
    assert vram._smi_path() is None                               # no driver: unknown, not the planted one
    (windows / "System32").mkdir(parents=True)
    (windows / "System32" / "nvidia-smi.exe").write_bytes(b"")
    assert vram._smi_path() == str(windows / "System32" / "nvidia-smi.exe")


# -- measurements -----------------------------------------------------------------


def test_ollama_ps_gives_each_models_vram():
    payload = {"models": [
        {"name": "qwen3.5:9b", "size_vram": 7_300 * vram.MB},
        {"model": "qwen3.5:4b", "size_vram": 3_100 * vram.MB},
        {"name": "on-the-cpu", "size_vram": 0},
        {"name": "odd", "size_vram": True},
        "junk",
    ]}
    assert vram.parse_ollama_ps(payload) == {"qwen3.5:9b": 7300, "qwen3.5:4b": 3100}
    assert vram.parse_ollama_ps({"models": []}) == {} and vram.parse_ollama_ps(None) == {}


def test_a_model_spilled_to_the_cpu_is_a_resident_but_not_a_measurement():
    payload = {"models": [
        {"name": "whole", "size": 7_300 * vram.MB, "size_vram": 7_300 * vram.MB},
        {"name": "spilled", "size": 20_000 * vram.MB, "size_vram": 9_000 * vram.MB},
        {"name": "no-size", "size_vram": 3_000 * vram.MB},
    ]}
    assert vram.parse_ollama_ps(payload) == {"whole": 7300, "spilled": 9000, "no-size": 3000}
    assert vram.parse_ollama_ps(payload, whole_only=True) == {"whole": 7300}


def test_a_load_is_measured_by_what_the_gpu_gained():
    before = vram.GpuMemory("GPU", 12288, 1200, 11088)
    after = vram.GpuMemory("GPU", 12288, 4300, 7988)
    assert vram.measured_delta(before, after) == 3100
    assert vram.measured_delta(after, before) is None             # something else let go meanwhile
    assert vram.measured_delta(None, after) is None
    assert vram.measured_delta(before, vram.GpuMemory("Other", 8192, 4300, 3892)) is None
    # NVML counts the driver's reservation in `used`, nvidia-smi does not: never mix them
    nvml_before = vram.GpuMemory("GPU", 12288, 1390, 10898, "nvml")
    smi_after = vram.GpuMemory("GPU", 12288, 4300, 7988, "smi")
    assert vram.measured_delta(nvml_before, smi_after) is None


def test_the_cache_ignores_non_numbers(tmp_path):
    path = tmp_path / "vram_measured.json"
    path.write_text('{"a": true, "b": "7", "c": 5000, "d": Infinity, "e": 1e400, "f": NaN}', encoding="utf-8")
    cache = vram.MeasuredCache(path)
    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (None, None, 5000)
    assert (cache.get("d"), cache.get("e"), cache.get("f")) == (None, None, None)   # no OverflowError
    cache.record("d", None)
    assert cache.get("d") is None


# -- large or small, and the load check ------------------------------------------------


def test_a_moe_with_experts_in_ram_is_not_large_but_unknown_is():
    assert vram.is_large(7300) and not vram.is_large(3100)
    assert vram.is_large(None)                                    # unsure: keep only one


def test_a_load_that_fits_once_the_old_model_goes_passes():
    gpu = vram.GpuMemory("GPU", 12288, 11000, 1288)
    check = vram.check_load("Qwen 9B", 7300, gpu, unloading=[vram.Resident("Qwen 35B", 7000)])
    assert check.fits is True and check.available_mb == 1288 + 7000 - 512 and check.message is None


def test_a_load_that_does_not_fit_names_what_holds_the_memory():
    gpu = vram.GpuMemory("GPU", 12288, 10500, 1788)
    residents = [vram.Resident("voice (GPT-SoVITS)", 2600), vram.Resident("helper qwen3.5:4b", 3100), vram.Resident("idle", 0)]
    check = vram.check_load("Qwen 9B", 7300, gpu, unloading=[vram.Resident("Qwen 35B", 3000)], residents=residents)
    assert check.fits is False and check.available_mb == 1788 + 3000 - 512
    # 10500 used - 3000 unloading - 5700 tracked = 1800 MB held by something we did not start
    assert [r.label for r in check.blockers] == ["helper qwen3.5:4b", "voice (GPT-SoVITS)", "other programs"]
    assert "Qwen 9B needs about 7.2 GB" in check.message and "only 4.1 GB would be free" in check.message
    assert "helper qwen3.5:4b (3.0 GB), voice (GPT-SoVITS) (2.5 GB), other programs (1.7 GB)" in check.message


def test_a_near_miss_never_prints_the_same_number_twice():
    check = vram.check_load("Qwen 9B", 7300, vram.GpuMemory("GPU", 12288, 4488, 7800))
    assert check.fits is False and check.available_mb == 7288                # short by 12 MB
    assert "needs about 7.2 GB" in check.message and "only 7.1 GB would be free" in check.message


def test_a_model_bigger_than_the_card_says_so_instead_of_blaming_residents():
    gpu = vram.GpuMemory("GPU", 12288, 3000, 9288)
    check = vram.check_load("Qwen 32B", 20_280, gpu, residents=[vram.Resident("voice (GPT-SoVITS)", 2600)])
    assert check.fits is False and check.blockers == ()
    assert check.message == "Qwen 32B needs about 19.9 GB of graphics memory, more than this GPU has (12.0 GB)."


def test_an_unknown_size_or_gpu_never_blocks_a_load():
    gpu = vram.GpuMemory("GPU", 12288, 12000, 288)
    assert vram.check_load("MoE", None, gpu).fits is None
    unknown_gpu = vram.check_load("Qwen 9B", 7300, None)
    assert unknown_gpu.fits is None and unknown_gpu.available_mb is None and unknown_gpu.message is None


# -- the kernel's view: snapshot and plan (numbers measured on the dev PC, 2026-11-15) --

RTX = vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 11893, 394, "nvml")
PS = {
    "models": [
        {"name": "qwen3.5:9b", "size": 5590 * vram.MB, "size_vram": 5590 * vram.MB},
        {"name": "qwen3.5:4b", "size": 3207 * vram.MB, "size_vram": 3207 * vram.MB},
        {"name": "nomic-embed-text:latest", "size": 320 * vram.MB, "size_vram": 320 * vram.MB},
        {"name": "spilled:7b", "size": 5000 * vram.MB, "size_vram": 2000 * vram.MB},   # partly on the CPU
    ]
}
NINE, FOUR, EMBED = "local:ollama/qwen3.5:9b", "local:ollama/qwen3.5:4b", "local:ollama/nomic-embed-text"
HELPERS = {FOUR, EMBED}   # a llama.cpp-style setup: the 4B classifier beside the chat model


@pytest.mark.asyncio
async def test_a_snapshot_names_what_holds_the_gpu_and_remembers_whole_models(monkeypatch):
    async def gpu():
        return RTX

    async def ps():
        return PS

    monkeypatch.setattr(vram, "gpu_memory", gpu)
    vram.MEASURED.record("local:llamacpp/big", 3100)
    snap = await vram.snapshot(ps, llamacpp_preset="big")
    assert snap.gpu == RTX
    assert snap.held == {NINE: 5590, FOUR: 3207, EMBED: 320, "local:ollama/spilled:7b": 2000, "local:llamacpp/big": 3100}
    # what a model needs is only learnt from a model held whole
    assert (vram.MEASURED.get(NINE), vram.MEASURED.get("local:ollama/spilled:7b")) == (5590, None)
    # an unmeasured llama-server holds an unknown amount
    assert (await vram.snapshot(ps, llamacpp_preset="other")).held["local:llamacpp/other"] is None


@pytest.mark.asyncio
async def test_no_gpu_reading_means_no_snapshot_and_no_ollama_call():
    async def ps():
        raise AssertionError("not asked")

    assert await vram.snapshot(ps) == vram.Snapshot(None)


def test_the_plan_frees_the_other_chat_model_and_keeps_the_helpers():
    snap = vram.Snapshot(RTX, {NINE: 5590, FOUR: 3207, EMBED: 320})
    label = lambda ref: ref.rsplit("/", 1)[1]   # noqa: E731
    # already in VRAM: nothing to load
    assert vram.plan(NINE, "9B", 5590, snap, helpers=HELPERS, label_of=label).fits is True
    # the 9B makes room: 394 + 5590 - 512 = 5472 MB for the newcomer
    fits = vram.plan("local:ollama/qwen3:8b", "8B", 5400, snap, helpers=HELPERS, label_of=label)
    assert fits.fits is True and fits.available_mb == 5472
    refused = vram.plan("local:ollama/gemma:12b", "Gemma 12B", 8200, snap, helpers=HELPERS, label_of=label)
    assert refused.fits is False
    assert [r.label for r in refused.blockers] == ["qwen3.5:4b", "other programs", "nomic-embed-text"]
    assert refused.message.startswith("Gemma 12B needs about 8.1 GB of graphics memory, but only 5.3 GB would be free.")
    # the room an unmeasured model frees is unknown: never refuse on a guess
    unknown = vram.Snapshot(RTX, {"local:llamacpp/big": None, FOUR: 3207})
    assert vram.plan(NINE, "9B", 8200, unknown, helpers=HELPERS, label_of=label).fits is None


def test_a_models_need_is_measured_else_estimated(tmp_path):
    from config import VramConfig

    cfg = VramConfig(kv_mb_per_1k_ctx=128, margin_mb=512)
    assert vram.need_for(NINE, file_bytes=6_600_000_000, ctx=8192, cfg=cfg) == 6294 + 1024 + 512
    vram.MEASURED.record(NINE, 5590)
    assert vram.need_for(NINE, file_bytes=6_600_000_000, ctx=8192, cfg=cfg) == 5590
    assert vram.need_for("local:llamacpp/big", file_bytes=20 * 2**30, ctx=8192, cfg=cfg, experts_on_cpu=True) is None


@pytest.mark.asyncio
async def test_a_load_that_will_not_fit_is_refused_before_anything_is_unloaded(monkeypatch):
    # FR-M-6: the model that is up stays up; the loader shows the reason (K1-09)
    import boot
    import llm
    import router
    from router import listing

    done = []

    class Rt:
        async def stop_llamacpp(self):
            done.append("stop llama-server")
            return True

    async def refuse(ref, rt):
        return vram.LoadCheck(False, 8200, 5472, (), "Gemma 12B needs about 8.1 GB of graphics memory, but only 5.3 GB would be free.")

    async def load(model):
        done.append(f"load {model}")

    monkeypatch.setattr(router, "get_router", lambda: Rt())
    monkeypatch.setattr(listing, "load_check", refuse)
    monkeypatch.setattr(llm, "load_model", load)
    with pytest.raises(vram.VramFullError, match="Gemma 12B needs about 8.1 GB"):
        await boot.load_chat_model("local:ollama/gemma3:12b")
    assert done == []


# -- Unload X (K1-09b, SPEC §5, D-071) ----------------------------------------------


def test_a_refusal_knows_which_blocker_is_which_model():
    snap = vram.Snapshot(RTX, {NINE: 5590, FOUR: 3207, EMBED: 320})
    refused = vram.plan("local:ollama/gemma:12b", "Gemma 12B", 8200, snap, helpers=HELPERS, label_of=lambda r: r)
    assert [(b.label, b.ref) for b in refused.blockers] == [
        (FOUR, FOUR), ("other programs", None), (EMBED, EMBED),
    ]


def test_unload_is_offered_only_for_a_model_that_stays_unloaded(monkeypatch):
    import dataclasses

    import boot
    from config import CONFIG

    cfg = dataclasses.replace(
        CONFIG,
        models=dataclasses.replace(CONFIG.models, local={**CONFIG.models.local, "reflex": "qwen3.5:9b", "classifier": "qwen3.5:4b"}),
        memory=dataclasses.replace(CONFIG.memory, embedding=dataclasses.replace(CONFIG.memory.embedding, model="nomic-embed-text")),
    )
    monkeypatch.setattr(boot, "CONFIG", cfg)
    blockers = (
        vram.Resident("qwen3.5:9b", 5590, NINE),          # the memory writer: loaded again only at a memory pass
        vram.Resident("qwen3.5:4b", 3207, FOUR),          # the classifier: no longer warmed (D-072)
        vram.Resident("other programs", 2700),
        vram.Resident("nomic-embed-text", 320, EMBED),    # embeddings: warmed again too
        vram.Resident("big", 9000, "local:llamacpp/big"),
    )
    assert [b.ref for b in boot.can_unload(blockers)] == [NINE, FOUR]


@pytest.mark.asyncio
async def test_the_refusal_carries_what_may_be_unloaded(monkeypatch):
    import boot
    import router
    from router import listing

    held = vram.Resident("qwen3.5:9b", 5590, NINE)

    async def refuse(ref, rt):
        return vram.LoadCheck(False, 8200, 5472, (held, vram.Resident("other programs", 2700)), "It needs about 8.1 GB.")

    monkeypatch.setattr(router, "get_router", lambda: object())
    monkeypatch.setattr(listing, "load_check", refuse)
    monkeypatch.setattr(boot, "can_unload", lambda blockers: tuple(b for b in blockers if b.ref))
    with pytest.raises(vram.VramFullError) as refused:
        await boot.load_chat_model("local:ollama/gemma3:12b")
    assert refused.value.unload == (held,)
