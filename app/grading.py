"""Second opinion from Claude on full-sentence answers, plus a word diff.

Exact matching is right for single words and short forms, but a translation
drill has many correct answers: "Te quería pedir un favor" and "Quería
pedirte un favor" are both right. When a sentence answer misses the model
answer, the drill asks Claude whether it is still correct Spanish that keeps
the grammar point being drilled. Without credentials, or if the call fails,
grading stays exact."""
import difflib
import json
import re
import unicodedata

from conversation import FALLBACK_BETA, MODEL, anthropic

# Answers this long count as sentences even without final punctuation.
MIN_WORDS = 4

_SYSTEM = """You grade one answer in a Spanish drill for an adult B1-B2 learner.

You get the exercise prompt (usually an English sentence to translate, sometimes naming the grammar point), the model answer, notes on the exercise, and the learner's answer.

Mark the answer correct when it is natural, grammatical Spanish that means the same thing as the model answer AND uses the grammar the exercise is practicing (for example: an imperfect drill needs the imperfect, a pluscuamperfecto drill needs había + participle, an "ir + gerundio" drill needs that construction). Accept normal variation: pronoun placement (te quería pedir / quería pedirte), dropped or added subject pronouns, synonyms, word order, Spain vs. Latin American usage. Ignore missing accents and punctuation.

Mark it incorrect for a wrong tense or mood, broken agreement, a wrong or missing word that changes the meaning, or avoiding the target grammar.

feedback: one short sentence in English. If incorrect, name the main error. If correct but different from the model answer, you may note the difference; otherwise leave it empty."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["correct", "feedback"],
    "additionalProperties": False,
}


def eligible(item):
    """Typed sentence answers only, where paraphrases are common ("Tenía
    cansancio." / "Estaba cansado."). Single words and short forms (se lo,
    no hables) have one right answer, and a multiple-choice pick is graded
    against its options."""
    target = item["target_form"].strip()
    is_sentence = target.endswith((".", "?", "!", "…")) or len(target.split()) >= MIN_WORDS
    return not item.get("choices") and is_sentence


def judge(client, item, answer):
    """Ask Claude whether `answer` is a correct alternative to the model
    answer. Returns {"correct": bool, "feedback": str}, or None when no
    verdict could be had (API error, refusal, truncation) - the caller then
    keeps the exact-match verdict."""
    user = (
        f"Exercise prompt: {item['prompt']}\n"
        f"Exercise type: {item.get('exercise_type', '')}\n"
        f"Model answer: {item['target_form']}\n"
        f"Notes: {item.get('explanation', '')}\n"
        f"Learner's answer: {answer}"
    )
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except (anthropic.APIError, TypeError):
        # TypeError: the SDK found no credentials at all (see conversation.py).
        return None
    if response.stop_reason in ("refusal", "max_tokens"):
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    try:
        verdict = json.loads(text)
        return {"correct": bool(verdict["correct"]), "feedback": str(verdict.get("feedback", "")).strip()}
    except (TypeError, ValueError, KeyError):
        return None


def _key(token):
    """Compare words ignoring case, accents and punctuation."""
    token = re.sub(r"[¿?¡!.,;:]", "", token.lower())
    return "".join(c for c in unicodedata.normalize("NFD", token) if unicodedata.category(c) != "Mn")


def _md(tokens):
    # Keep the learner's text from being read as Markdown formatting.
    return " ".join(re.sub(r"([\\*_~`])", r"\\\1", t) for t in tokens)


def word_diff(answer, target):
    """Markdown showing how the answer differs from the model answer, word by
    word: ~~words to drop~~ and **words that should be there**. None when
    there is nothing useful to show (empty answer, one-word target, or an
    answer too different for a word-by-word comparison to help)."""
    mine, theirs = answer.split(), target.split()
    if not mine or len(theirs) < 2:
        return None
    matcher = difflib.SequenceMatcher(None, [_key(t) for t in mine], [_key(t) for t in theirs], autojunk=False)
    if matcher.ratio() < 0.4:
        return None  # a different sentence altogether: striking it all out teaches nothing
    parts = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            parts.append(_md(theirs[j1:j2]))
        if op in ("replace", "delete"):
            parts.append(f"~~{_md(mine[i1:i2])}~~")
        if op in ("replace", "insert"):
            parts.append(f"**{_md(theirs[j1:j2])}**")
    return " ".join(parts)
