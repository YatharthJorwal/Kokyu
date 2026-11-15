"""VRAM manager v1 (K1-09; FR-M-3, FR-M-6; ARCHITECTURE §7.3).

Pure helpers; `model_loader` decides what to load, unload or refuse.

- **Reads the GPU's memory**: NVML straight from the driver's `nvml.dll` (ctypes,
  no package), else the `nvidia-smi` that ships with every NVIDIA driver, else
  "unknown". Both are loaded by full path only. More than one NVIDIA GPU is
  "unknown" too: which card a backend uses is not ours to guess (v1).
  `read_gpu()` blocks: call it with `asyncio.to_thread` (or `gpu_memory()`).
- **Remembers what models really took**: Ollama's `/api/ps` `size_vram`
  (`parse_ollama_ps`) or the GPU-wide change around a `llama-server` start
  (`measured_delta`), cached in `data/vram_measured.json`; beats any estimate.
- **Estimates** a model it has not seen: file size + KV cache + margin. A MoE with
  its experts on the CPU has no useful file-size estimate: "unknown" until measured.
- **Large or small** (`is_large`): only one large LLM may be resident across
  Ollama and llama.cpp; a MoE with experts in RAM (~3 GB) is not large.
- **Fits hint and load check** (`fits`, `check_load`): would the model fit in
  what is free now plus what is being unloaded, minus headroom? If not, the
  check names what holds the memory. `None` = unknown: never refuse on a guess.
- **The kernel's view** (`snapshot`, `need_for`, `plan`): the GPU now and the
  models holding it (Ollama's `/api/ps`, the running `llama-server`), and what
  loading one more would unload (other chat models) and keep (the helpers).
  `router/listing.py` turns it into the picker's hints, `boot.py` into the
  check before a load.
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import math
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import paths

MB = 1024 * 1024
NVML_SUCCESS = 0


@dataclass(frozen=True)
class GpuMemory:
    name: str
    total_mb: int
    used_mb: int
    free_mb: int
    # "nvml" or "smi": their `used` differs (NVML counts the driver's reservation),
    # so a before/after measurement must not mix them.
    source: str = field(default="", compare=False)


# -- reading the GPU --------------------------------------------------------------


class _NvmlMemory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


def _driver_files(windows_name: str) -> list[Path]:
    """Where the NVIDIA driver puts `windows_name`, as full paths. A bare name would
    follow the search order, which on Windows tries the current directory first."""
    found = []
    windir = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if windir:
        found.append(Path(windir) / "System32" / windows_name)          # current drivers
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        found.append(Path(program_files) / "NVIDIA Corporation" / "NVSMI" / windows_name)   # older drivers
    return found


def _nvml_candidates() -> list[Path]:
    if sys.platform == "win32":
        return _driver_files("nvml.dll")
    return [Path("/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1"), Path("/usr/lib64/libnvidia-ml.so.1")]


def _smi_path() -> str | None:
    if sys.platform == "win32":
        return next((str(p) for p in _driver_files("nvidia-smi.exe") if p.is_file()), None)
    found = shutil.which("nvidia-smi")              # POSIX `which` never adds the cwd
    return found if found and os.path.isabs(found) else None


def _load_nvml() -> Any | None:
    for candidate in _nvml_candidates():
        if candidate.is_file():
            try:
                return ctypes.CDLL(str(candidate))
            except OSError:
                continue
    return None


def _read_nvml(load: Callable[[], Any | None] = _load_nvml) -> GpuMemory | None:
    """The first GPU through NVML, or None if there is no driver library or it fails."""
    try:
        lib = load()
        if lib is None or lib.nvmlInit_v2() != NVML_SUCCESS:
            return None
    except (OSError, AttributeError):
        return None
    try:
        count = ctypes.c_uint(0)
        handle = ctypes.c_void_p()
        memory = _NvmlMemory()
        name = ctypes.create_string_buffer(96)                  # NVML_DEVICE_NAME_V2_BUFFER_SIZE
        if lib.nvmlDeviceGetCount_v2(ctypes.byref(count)) != NVML_SUCCESS or count.value != 1:
            return None                                         # none, or several: unknown
        if lib.nvmlDeviceGetHandleByIndex_v2(ctypes.c_uint(0), ctypes.byref(handle)) != NVML_SUCCESS:
            return None
        if lib.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(memory)) != NVML_SUCCESS:
            return None
        if lib.nvmlDeviceGetName(handle, name, ctypes.c_uint(len(name))) != NVML_SUCCESS:
            name.value = b"NVIDIA GPU"
        return GpuMemory(
            name.value.decode("utf-8", "replace"), memory.total // MB, memory.used // MB, memory.free // MB, "nvml"
        )
    except (OSError, AttributeError, ValueError):
        return None
    finally:
        try:
            lib.nvmlShutdown()
        except (OSError, AttributeError):
            pass


def parse_smi(text: str) -> GpuMemory | None:
    """One line of `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free
    --format=csv,noheader,nounits`: the GPU, or None unless there is exactly one."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            total, used, free = (int(float(p)) for p in parts[1:])
        except ValueError:
            continue
        gpus.append(GpuMemory(parts[0], total, used, free, "smi"))
    return gpus[0] if len(gpus) == 1 else None


def _read_smi(run: Callable[..., Any] = subprocess.run) -> GpuMemory | None:
    exe = _smi_path()
    if exe is None:
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        result = run(
            [exe, "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return parse_smi(result.stdout)


def read_gpu() -> GpuMemory | None:
    """Blocking (DLL call or a subprocess). Use `gpu_memory()` from async code."""
    return _read_nvml() or _read_smi()


async def gpu_memory() -> GpuMemory | None:
    return await asyncio.to_thread(read_gpu)


# -- measured footprints --------------------------------------------------------


class MeasuredCache:
    """model ref -> measured VRAM in MB, kept across runs (ARCHITECTURE §7.3).
    File I/O: call `get`/`record` with `asyncio.to_thread` from async code."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._data: dict[str, int] | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        # Resolved on use, so a redirected data dir (tests, KOKYU_DATA_DIR) is followed.
        return self._path or (paths.app_data_dir() / "vram_measured.json")

    def _load(self) -> dict[str, int]:
        if self._data is None:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._data = {
                    str(k): int(v) for k, v in raw.items()
                    if _number(v) and v > 0
                }
            except (OSError, ValueError, AttributeError):
                self._data = {}
        return self._data

    def get(self, ref: str) -> int | None:
        with self._lock:
            return self._load().get(ref)

    def record(self, ref: str, mb: int | None) -> None:
        if not mb or mb <= 0:
            return
        with self._lock:
            data = self._load()
            if data.get(ref) == int(mb):
                return
            data[ref] = int(mb)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass  # a cache, not a record: the estimate still works


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_ollama_ps(payload: Any, *, whole_only: bool = False) -> dict[str, int]:
    """Ollama `/api/ps` -> {model name: VRAM in MB}, models with none on the GPU left
    out. What a model holds now (residents): every entry. What it *needs* (the
    measured cache): `whole_only=True`, because a model partly spilled to the CPU took
    less than it needs, and recording that would call it a fit next time."""
    models = payload.get("models") if isinstance(payload, Mapping) else None
    found: dict[str, int] = {}
    for entry in models if isinstance(models, list) else []:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name") or entry.get("model")
        vram_bytes, size = entry.get("size_vram"), entry.get("size")
        if not isinstance(name, str) or not _number(vram_bytes) or vram_bytes <= 0:
            continue
        if whole_only and (not _number(size) or vram_bytes < size):
            continue
        found[name] = max(1, int(vram_bytes) // MB)
    return found


def measured_delta(before: GpuMemory | None, after: GpuMemory | None) -> int | None:
    """What a load took, GPU-wide: used after minus used before. Read `before` once the
    other backend has unloaded, `after` once the server is ready. None if unknown,
    read two different ways (NVML and nvidia-smi count `used` differently), or
    nothing grew (something else freed memory meanwhile)."""
    if before is None or after is None or before.total_mb != after.total_mb or before.source != after.source:
        return None
    grew = after.used_mb - before.used_mb
    return grew if grew > 0 else None


# -- estimates, large or small, and the fits hint --------------------------------


def estimate_mb(
    *,
    measured: int | None,
    file_bytes: int | None,
    ctx: int,
    kv_mb_per_1k_ctx: int,
    margin_mb: int,
    override_mb: int | None = None,
    experts_on_cpu: bool = False,
) -> int | None:
    """Best guess of a model's VRAM: an explicit override, else what it measured
    last time, else file + KV cache + margin. None when there is nothing to go on
    (or a MoE with its experts in RAM, where the file size says nothing)."""
    if override_mb:
        return int(override_mb)
    if measured:
        return int(measured)
    if experts_on_cpu or not file_bytes:
        return None
    return int(file_bytes / MB + kv_mb_per_1k_ctx * max(ctx, 0) / 1024 + margin_mb)


def is_large(mb: int | None, *, large_mb: int = 4096) -> bool:
    """Large LLMs are exclusive across backends (§7.3). Unknown counts as large:
    when unsure, unload the other one rather than run out of memory."""
    return mb is None or mb >= large_mb


def fits(need_mb: int | None, gpu: GpuMemory | None, *, freed_mb: int = 0, headroom_mb: int = 512) -> bool | None:
    """Would `need_mb` fit once the current chat model (`freed_mb`) is unloaded?
    None = unknown (no GPU reading or no estimate)."""
    if need_mb is None or gpu is None:
        return None
    return need_mb <= gpu.free_mb + max(freed_mb, 0) - headroom_mb


@dataclass(frozen=True)
class Resident:
    """Something holding VRAM: a model, the TTS backend, the renderer."""

    label: str
    mb: int
    ref: str | None = None      # a model's ref; None for "other programs" (K1-09b)


@dataclass(frozen=True)
class LoadCheck:
    fits: bool | None           # None: unknown, so the load goes ahead
    need_mb: int | None
    available_mb: int | None    # free now + unloaded - headroom
    blockers: tuple[Resident, ...] = ()
    message: str | None = None  # set only when it does not fit


def _gb(mb: int, *, up: bool) -> str:
    """One decimal, rounded the way that keeps "needs" above "free" in a refusal."""
    tenths = mb / 1024 * 10
    return f"{(math.ceil(tenths) if up else math.floor(tenths)) / 10:.1f} GB"


def check_load(
    label: str,
    need_mb: int | None,
    gpu: GpuMemory | None,
    *,
    unloading: Iterable[Resident] = (),
    residents: Iterable[Resident] = (),
    headroom_mb: int = 512,
) -> LoadCheck:
    """The verdict for loading `label`. `unloading`: what goes first (its memory
    counts as free). `residents`: what stays; when the model does not fit they are
    named, largest first, with whatever else holds memory as "other programs", so
    the user knows what to close."""
    freed = sum(max(r.mb, 0) for r in unloading)
    verdict = fits(need_mb, gpu, freed_mb=freed, headroom_mb=headroom_mb)
    available = None if gpu is None else max(gpu.free_mb + freed - headroom_mb, 0)
    if verdict is not False or gpu is None or need_mb is None:
        return LoadCheck(verdict, need_mb, available)
    needs = f"{label} needs about {_gb(need_mb, up=True)} of graphics memory"
    if need_mb > gpu.total_mb - headroom_mb:     # closing things would not help
        return LoadCheck(False, need_mb, available, (), f"{needs}, more than this GPU has ({_gb(gpu.total_mb, up=False)}).")
    held = [r for r in residents if r.mb > 0]
    other = gpu.used_mb - freed - sum(r.mb for r in held)
    if other >= 256:                              # below that: the desktop and rounding
        held.append(Resident("other programs", other))
    blockers = tuple(sorted(held, key=lambda r: r.mb, reverse=True))
    message = f"{needs}, but only {_gb(available or 0, up=False)} would be free."
    if blockers:
        message += " In use: " + ", ".join(f"{r.label} ({_gb(r.mb, up=False)})" for r in blockers) + "."
    return LoadCheck(False, need_mb, available, blockers, message)


# -- the kernel's view (K1-09): what holds the GPU, what a model needs, the verdict --

MEASURED = MeasuredCache()


class VramFullError(RuntimeError):
    """A load refused before it started: the message names what holds the memory;
    `unload` lists the models the card may offer to unload (K1-09b, D-071)."""

    def __init__(self, message: str, unload: Iterable[Resident] = ()) -> None:
        super().__init__(message)
        self.unload = tuple(unload)


@dataclass(frozen=True)
class Snapshot:
    """The GPU now and the models holding it: model ref -> MB (None: held, size unknown)."""

    gpu: GpuMemory | None
    held: Mapping[str, int | None] = field(default_factory=dict)


def ollama_ref(name: str) -> str:
    return f"local:ollama/{name.removesuffix(':latest')}"


async def snapshot(ollama_ps: Callable[[], Awaitable[Any]], llamacpp_preset: str | None = None) -> Snapshot:
    """Reads the GPU and asks Ollama what it holds (`ollama_ps` returns `/api/ps`'s
    JSON or None). Records every model Ollama holds whole as measured. A running
    llama-server holds its measured size, or an unknown amount."""
    gpu = await gpu_memory()
    if gpu is None:
        return Snapshot(None)
    payload = await ollama_ps()
    held: dict[str, int | None] = {ollama_ref(n): mb for n, mb in parse_ollama_ps(payload).items()}
    for name, mb in parse_ollama_ps(payload, whole_only=True).items():
        await asyncio.to_thread(MEASURED.record, ollama_ref(name), mb)
    if llamacpp_preset:
        ref = f"local:llamacpp/{llamacpp_preset}"
        held[ref] = await asyncio.to_thread(MEASURED.get, ref)
    return Snapshot(gpu, held)


def need_for(ref: str, *, file_bytes: int | None, ctx: int, cfg: Any, experts_on_cpu: bool = False) -> int | None:
    """A model's VRAM: measured, else estimated (`cfg`: config.VramConfig). Reads
    the measured cache: call it off the event loop."""
    return estimate_mb(
        measured=MEASURED.get(ref),
        file_bytes=file_bytes,
        ctx=ctx,
        kv_mb_per_1k_ctx=cfg.kv_mb_per_1k_ctx,
        margin_mb=cfg.margin_mb,
        experts_on_cpu=experts_on_cpu,
    )


def plan(
    ref: str,
    label: str,
    need_mb: int | None,
    snap: Snapshot,
    *,
    helpers: Iterable[str],
    label_of: Callable[[str], str],
    headroom_mb: int = 512,
) -> LoadCheck:
    """Loading `ref` as the chat model: the other chat models make room (the kernel
    or Ollama unloads them), the helpers stay (they run beside every reply)."""
    if ref in snap.held:
        return LoadCheck(True, need_mb, None)        # already in VRAM
    keep = set(helpers)
    leaving = {r: mb for r, mb in snap.held.items() if r not in keep}
    if any(mb is None for mb in leaving.values()):
        return LoadCheck(None, need_mb, None)        # room an unmeasured model frees: unknown
    return check_load(
        label,
        need_mb,
        snap.gpu,
        unloading=[Resident(label_of(r), mb or 0, r) for r, mb in leaving.items()],
        residents=[Resident(label_of(r), mb or 0, r) for r, mb in snap.held.items() if r in keep],
        headroom_mb=headroom_mb,
    )
