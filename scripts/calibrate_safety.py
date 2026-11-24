"""Calibrates the self-harm detector's meaning check (D-121, SAFE-02) against the real
embedder in config (`nomic-embed-text` through Ollama). Needs Ollama running with that
model; never run by tests.

    .venv/Scripts/python.exe scripts/calibrate_safety.py

Lines alternate into a calibration half and a held-out half. For each threshold pair it
prints, on the calibration half, how many help-needed lines the whole detector catches
and how many ordinary lines it flags; then the chosen pair on the held-out half.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "KASANE"))

import safety  # noqa: E402

# Not the detector's own examples. Help-needed: mostly said without the words the
# patterns know. Ordinary: sadness, tiredness, idioms, games and stories, other people.
NEEDS_HELP = [
    "what's the point of anything anymore",
    "I just want it all to be over",
    "I don't think I'll be here next week",
    "I've been saying goodbye to people",
    "everything would be easier if I wasn't here",
    "I keep thinking about how I'd do it",
    "I've been looking up how high the bridge is",
    "I can't take this pain anymore, I want out of life",
    "I'm not going to be a problem for anyone much longer",
    "I've stopped caring whether I live",
    "sometimes I hope I don't wake up tomorrow",
    "I've got the pills lined up on my desk",
    "I scratch my skin until it bleeds",
    "I burned my arm with a lighter again",
    "nobody would care if I disappeared for good",
    "I feel like dying is the only way out",
    "this is my last message to anyone",
    "I want to stop existing",
    "I've been planning my death",
    "I'm going to jump",
    "living hurts too much",
    "I deserve to die",
    "I want to sleep forever",
    "my family would be better without me around",
    "I already wrote the note",
    "I hate being alive",
    "I punched the wall until my hand broke because I deserve the pain",
    "I'm ready to go, I've made peace with it",
]

ORDINARY = [
    "I had a terrible day at work",
    "I'm so lonely lately",
    "I failed my exam and I'm upset",
    "this game is so hard I want to throw my controller",
    "my dog died last month",
    "I'm exhausted, I need a vacation",
    "the hero sacrifices himself to save the city",
    "my ex broke my heart",
    "I'm stressed about money",
    "I could sleep for a week",
    "that movie killed me, so funny",
    "I want to disappear from social media for a while",
    "I'm going to jump into the pool",
    "my mom is in the hospital",
    "I hate my job so much",
    "I feel like nobody understands me",
    "I'm done with this semester",
    "the villain plans to poison the king",
    "I nearly fell off the ladder today",
    "I'm going to bed, goodnight",
    "I feel empty today",
    "I'm tired of being single",
    "I bought new pills for my headache",
    "we read a poem about death in class",
    "I'm so sick of this weather",
    "write me a sad story about a soldier",
    "I miss my grandpa",
    "I'm dying of boredom",
]


def _cos(a: list[float], b: list[float]) -> float:
    return safety._cosine(a, b)


async def scores(lines: list[str]) -> list[tuple[str, bool, float, float]]:
    help_vecs, calm_vecs = await safety._example_vectors()
    checked = [safety.user_line_text(line, False) for line in lines]
    vectors = await safety._embed_many(checked)
    out = []
    for line, text, v in zip(lines, checked, vectors):
        out.append((line, safety._pattern_hit(text), max(_cos(v, h) for h in help_vecs), max(_cos(v, c) for c in calm_vecs)))
    return out


def flagged(row: tuple[str, bool, float, float], floor: float, margin: float) -> bool:
    _, pattern, h, c = row
    return pattern or (len(row[0].split()) >= 3 and h >= floor and h - c >= margin)


async def main() -> None:
    pos = await scores(NEEDS_HELP)
    neg = await scores(ORDINARY)
    print("help-needed lines: pattern, nearest help, nearest look-alike")
    for line, p, h, c in pos:
        print(f"  {'P' if p else ' '} {h:.3f} {c:.3f} {h - c:+.3f}  {line}")
    print("ordinary lines:")
    for line, p, h, c in neg:
        print(f"  {'P' if p else ' '} {h:.3f} {c:.3f} {h - c:+.3f}  {line}")

    cal_pos, held_pos = pos[0::2], pos[1::2]
    cal_neg, held_neg = neg[0::2], neg[1::2]
    print("\ncalibration half: floor margin caught/of flagged-ordinary/of")
    grid = []
    for f100 in range(50, 91, 2):
        for m100 in range(0, 11, 1):
            floor, margin = f100 / 100, m100 / 100
            tp = sum(flagged(r, floor, margin) for r in cal_pos)
            fp = sum(flagged(r, floor, margin) for r in cal_neg)
            grid.append((fp, -tp, floor, margin))
    for fp, ntp, floor, margin in sorted(grid)[:15]:
        print(f"  {floor:.2f} {margin:.2f}  {-ntp}/{len(cal_pos)}  {fp}/{len(cal_neg)}")
    if len(sys.argv) == 3:
        floor, margin = float(sys.argv[1]), float(sys.argv[2])
        tp = sum(flagged(r, floor, margin) for r in held_pos)
        fp = sum(flagged(r, floor, margin) for r in held_neg)
        print(f"\nheld-out half at {floor} {margin}: caught {tp}/{len(held_pos)}, flagged ordinary {fp}/{len(held_neg)}")
        for r in held_pos + held_neg:
            print(f"  {'FLAG' if flagged(r, floor, margin) else '    '} {r[0]}")


asyncio.run(main())
