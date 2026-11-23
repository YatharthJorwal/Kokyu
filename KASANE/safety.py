"""
The self-harm detector (D-121): a line about suicide or self-harm gets no reply, only
a card that points to help; a reply that encourages it, or gives a method, is stopped.

Local only, in every mode, and the same for every companion. Two layers on the user's
line, one on her reply:

1. Patterns for first-person suicide and self-harm talk. A match is dropped when a
   negation sits right before it ("I would never kill myself"); some patterns also need
   the speaker in the clause ("I", "me"), so other people's deaths and idioms such as
   "this traffic is killing me" stay out.
2. A meaning check with the memory embedder (`nomic-embed-text`, D-117): the line's
   nearest written example must be one of the help-needed ones, close enough and
   clearly closer than the nearest look-alike. It catches what no pattern lists
   ("I wrote the letters, I won't be around much longer"). If the embedder is down or
   slow, the patterns decide alone.
3. Her reply: patterns only (encouragement and methods), checked as it streams.

In a roleplay the user's *actions* are left out: they describe a character. What they
say, and anything out of character, is checked. Weak models follow prompt rules
unreliably, which is why this does not rely on the prompt line in prompting.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re

from config import CONFIG
from memory import embeddings

log = logging.getLogger("kasane.safety")

# Who is speaking: the pattern needs the user in the same clause.
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|im|i am|i've|ive|i'll|ill|i'd|me|my|myself)\b")
# A negation right before a match cancels it ("I'd never", "I'm not", "don't").
_NEGATION = re.compile(r"\b(?:not|never|no longer|wouldn't|wouldnt|won't|wont|don't|dont|didn't|didnt|doesn't|isn't|aren't|wasn't)\b")
_CLAUSE_END = re.compile(r"[.!?\n;]")
_ACTION = re.compile(r"\*[^*\n]+\*")

# (pattern, needs the speaker in the clause, a negation before it cancels it)
_USER_PATTERNS: tuple[tuple[re.Pattern[str], bool, bool], ...] = tuple(
    (re.compile(p), fp, neg)
    for p, fp, neg in (
        (r"\b(?:kill(?:ing|ed)?|hurt(?:ing)?|harm(?:ing|ed)?|cut(?:ting)?|hang(?:ing|ed)?|shoot(?:ing)?|drown(?:ing)?|starv(?:e|ing)|burn(?:ing)?|off(?:ing)?|end(?:ing)?)\s+my\s?self\b(?!\s+(?:out\b|some\b|a\s+(?:break|slice|piece)\b|short\b|free\b|loose\b|by\s+accident|accidentally|at\b|while\b|when\b|during\b|playing|shaving|cooking|lifting|training|working|laughing|trying|on\b(?!\s+purpose)))", False, True),
        (r"(?:^\s*|\b(?:to|gonna|wanna|i'?ll|i|just|might|literally|imma|ima)\s+)kms\b", False, True),
        (r"\bend(?:ing)?\s+(?:my\s+(?:own\s+)?life|it\s+all)\b", True, True),
        (r"\b(?:want|wanna|wish|ready|trying|tried|try|plan(?:ning)?|deserve)\s+(?:to\s+)?(?:die|be\s+dead|not\s+(?:wake\s+up|exist|be\s+alive|be\s+here))\b(?!\s+(?:of|from|for|laughing|inside|on\s+this\s+hill))", True, True),
        (r"\bwish\s+i\s+(?:was|were|had)\s+(?:dead|never\s+been\s+born|died)\b", False, True),
        (r"\b(?:commit(?:ting)?|attempt(?:ing|ed)?)\s+suicide\b", True, True),
        (r"\b(?:i'm|im|i\s+am|feel(?:ing)?|been|so|really)\s+(?:so\s+|really\s+|very\s+)?suicidal\b", False, True),
        (r"\b(?:my|a)\s+suicide\s+(?:note|letter|plan)\b", True, True),
        (r"\bthinking\s+(?:about|of)\s+(?:suicide|killing\s+myself|ending\s+(?:it|my\s+life))\b", True, True),
        (r"\b(?:don't|dont|do\s+not|no\s+longer|never)\s+want\s+to\s+(?:live|be\s+alive|exist|wake\s+up|be\s+here)\b(?!\s+(?:in|with|there|near|at|on|like|together|alone|here|by|without|anywhere|somewhere))", True, False),
        (r"\b(?:better\s+off|be\s+better)\s+(?:dead|without\s+me)\b", False, True),
        (r"\b(?:everyone|everybody|they|the\s+world|people)\s+(?:would\s+be|is|are|will\s+be)\s+better\s+(?:off\s+)?without\s+me\b", False, True),
        (r"\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:live|living|go(?:ing)?\s+on|be(?:ing)?\s+alive|stay(?:ing)?\s+alive)\b", False, False),
        (r"\b(?:cut(?:ting)?|burn(?:ing)?|hurt(?:ing)?|scratch(?:ing)?|slit(?:ting)?)\s+my\s+(?:wrists?|arms?|thighs?|legs?|skin|veins?)\b", False, True),
        (r"\bself[- ]?harm(?:ing|ed)?\b", True, True),
        (r"\b(?:i|i'm|im|i've|ive|i'll|ill|i'd|me|gonna|wanna)\s+(?:(?!he\b|she\b|they\b|my\b|his\b|her\b|their\b|someone\b|somebody\b)[\w']+\s+){0,3}?overdos(?:e|ing|ed)?\b", False, True),
        (r"\b(?:take|took|swallow(?:ed)?|taking)\s+(?:all|the\s+whole\s+bottle|every\s+one|the\s+rest)\s+of\s+(?:my|the|these|those)\s+(?:pills|tablets|meds|medication)\b", True, True),
        (r"\b(?:painless|quickest|easiest|best|fastest)\s+(?:way|ways|method)\s+to\s+(?:die|kill\s+myself|end\s+(?:it|my\s+life)|commit\s+suicide)\b", False, False),
        (r"\bhow\s+(?:many|much)\s+(?:pills|tablets|mg|sleeping\s+pills)\b[^.!?\n]{0,40}\b(?:die|kill\s+me|kill\s+myself|lethal|never\s+wake\s+up)\b", False, False),
        (r"\bnever\s+wake\s+up\b", True, True),
    )
)

# Her reply: encouraging self-harm, or a method. A negation inside the phrase is not
# allowed ("please don't hurt yourself" is care, not encouragement).
_NOT_NEG = r"(?:(?!don't|dont|not|never)\w+\s+){0,2}?"
_REPLY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\b(?:you\s+should|you\s+could|just|go(?:\s+and)?|why\s+don't\s+you|might\s+as\s+well|you\s+deserve\s+to|better\s+if\s+you)\s+" + _NOT_NEG + r"(?:kill|hurt|harm|cut|hang|end|off)\s+your\s?self\b",
        r"\bkys\b",
        r"\b(?:no\s*one|nobody)\s+(?:would|will|is\s+going\s+to|gonna)\s+(?:miss|care\s+about|notice)\s+(?:you|if\s+you)\b",
        r"\b(?:the\s+world|everyone|everybody)\s+(?:would\s+be|is|will\s+be)\s+better\s+(?:off\s+)?without\s+you\b",
        r"\b(?:slit|cut)\s+(?:your|my|her|his|their)?\s*wrists?\b",
        r"\blethal\s+dose\b",
        r"\b(?:tie|make|making|tying)\s+(?:a|the)\s+noose\b",
        r"\bhow\s+(?:many|much)\s+(?:pills|tablets|mg)\b[^.!?\n]{0,40}\b(?:die|lethal|kill|overdose)\b",
        r"\b(?:painless|quickest|easiest|fastest)\s+way\s+to\s+(?:die|kill\s+yourself|end\s+your\s+life)\b",
    )
)

# The meaning check's written examples (English). Help-needed lines, then look-alikes
# that are not: idioms, other people, games and stories, plain tiredness.
HELP_EXAMPLES: tuple[str, ...] = (
    "I want to kill myself",
    "I don't want to be alive anymore",
    "I've been thinking about ending my life",
    "Everyone would be better off without me",
    "I wrote letters to my family, I won't be around much longer",
    "I can't do this anymore, I just want everything to stop forever",
    "I'm going to take all my pills tonight",
    "I keep cutting my arms to feel something",
    "I've decided tonight is my last night",
    "I want to go to sleep and never wake up",
    "There's no point in living anymore",
    "I hate myself and want to disappear forever",
    "I hurt myself again last night",
    "I have a plan to end it",
    "I bought a rope for myself",
    "I'm standing on the edge of the bridge right now",
    "Life isn't worth living for me",
    "I'm a burden to everyone and I should just go away for good",
    "Goodbye, this is the last time we'll ever talk",
    "I've been hurting myself on purpose",
    "I'm so tired of being alive",
    "I tried to overdose before and I want to try again",
    "I don't see any way out except dying",
    "I want to die",
    "What's the most painless way to die",
    "I'm suicidal",
    "Nobody would even notice if I was gone forever",
    "I gave away my things because I won't need them anymore",
)
CALM_EXAMPLES: tuple[str, ...] = (
    "This traffic is killing me",
    "I'm dying to see that movie",
    "I could kill for a pizza right now",
    "My phone is dying, I need a charger",
    "I'm so tired after work today",
    "My grandmother died last year and I miss her",
    "I almost died laughing at that video",
    "That exam absolutely killed me",
    "My character dies at the end of the game",
    "I killed it at the presentation today",
    "I'm dead tired, going to bed",
    "I would die of embarrassment",
    "Let's play a game",
    "I hate Mondays so much",
    "I'm feeling a bit down today",
    "I want to go to sleep early tonight",
    "The plant in my room is dying",
    "I hurt my knee playing football",
    "I cut my finger while cooking dinner",
    "I'm done with this project, finally",
    "The villain wants to kill the hero",
    "My friend is going through a hard time",
    "I want to disappear into a good book this weekend",
    "I want to quit my job",
    "Goodbye, I'll talk to you tomorrow",
    "I'm bored, entertain me",
    "Please don't ever hurt yourself",
    "I would never hurt myself",
)

_PREFIX = "classification: "   # nomic-embed-text's task prefix
_examples: tuple[list[list[float]], list[list[float]]] | None = None
_examples_lock = asyncio.Lock()


def _normal(text: str) -> str:
    return text.lower().replace("’", "'").replace("‘", "'")


def _clause_before(text: str, start: int) -> str:
    """The text of the same clause before a match."""
    ends = [m.end() for m in _CLAUSE_END.finditer(text, 0, start)]
    return text[ends[-1] if ends else 0 : start]


def _pattern_hit(text: str) -> bool:
    for pattern, needs_speaker, negatable in _USER_PATTERNS:
        for match in pattern.finditer(text):
            before = _clause_before(text, match.start())
            if negatable and _NEGATION.search(before[-24:]):
                continue
            if needs_speaker and not (_FIRST_PERSON.search(before[-48:]) or _FIRST_PERSON.search(match.group())):
                continue
            return True
    return False


def user_line_text(text: str, roleplay: bool) -> str:
    """What is checked: in a roleplay, the line without its *actions*."""
    text = _normal(text)
    return _ACTION.sub(" ", text) if roleplay else text


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def _embed_many(texts: list[str]) -> list[list[float]]:
    """The detector's own door to the embedder (conftest stubs it for every test)."""
    return await embeddings.embed_many([_PREFIX + t for t in texts])


async def _example_vectors() -> tuple[list[list[float]], list[list[float]]]:
    global _examples
    async with _examples_lock:
        if _examples is None:
            vectors = await _embed_many(list(HELP_EXAMPLES) + list(CALM_EXAMPLES))
            _examples = (vectors[: len(HELP_EXAMPLES)], vectors[len(HELP_EXAMPLES) :])
        return _examples


async def _meaning_hit(text: str) -> bool:
    cfg = CONFIG.safety
    if len(text.split()) < 3:
        return False   # too short to mean anything the patterns did not catch
    try:
        help_vecs, calm_vecs = await asyncio.wait_for(_example_vectors(), cfg.examples_timeout_s)
        (line,) = await asyncio.wait_for(_embed_many([text]), cfg.embed_timeout_s)
    except (embeddings.EmbeddingUnreachableError, asyncio.TimeoutError, ValueError) as exc:
        log.info(f"safety: no meaning check for this line ({type(exc).__name__}); patterns only")
        return False
    nearest_help = max(_cosine(line, v) for v in help_vecs)
    nearest_calm = max(_cosine(line, v) for v in calm_vecs)
    return nearest_help >= cfg.similarity_floor and nearest_help - nearest_calm >= cfg.similarity_margin


async def needs_help(text: str, *, roleplay: bool = False) -> bool:
    """True when the user's line talks about suicide or self-harm (D-121)."""
    if not CONFIG.safety.enabled:
        return False
    checked = user_line_text(text, roleplay)
    if not checked.strip():
        return False
    if _pattern_hit(checked):
        return True
    return await _meaning_hit(checked)


class ReplyGuard:
    """Checks her reply as it streams: True once it encourages self-harm or gives a
    method. Only the tail is searched, so a long reply stays cheap."""

    TAIL = 600

    def hit(self, reply_so_far: str) -> bool:
        if not CONFIG.safety.enabled:
            return False
        tail = _normal(reply_so_far[-self.TAIL :])
        return any(p.search(tail) for p in _REPLY_PATTERNS)
