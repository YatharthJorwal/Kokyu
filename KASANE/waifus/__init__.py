"""Waifus: a companion is DATA (prompt, voice, VRM), never code (RULES R-01).

A pack is a folder: waifu.yaml, prompt.md, model.vrm, voice/ref.wav. Premade packs ship
read-only with the app (assets/premade/); user packs live in the data directory.
"""
from waifus.pack import (  # noqa: F401
    PackError,
    VoiceSpec,
    Waifu,
    load_pack,
    slugify,
)
from waifus.registry import (  # noqa: F401
    PackProblem,
    WaifuRegistry,
    get_registry,
    reset_registry,
)
