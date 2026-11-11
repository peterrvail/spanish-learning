"""Lesson screenshots -> staged observations -> compiled study data.

    run      hash, skip what is already read, one Claude vision call per new
             image, validate, mark duplicates, write staged/<sha12>.json
    review   pending -> approved / rejected (decisions are saved in the file)
    compile  approved observations -> data/compiled/lesson_observations.json,
             which the app reads (a flashcard deck and a corrections drill)

No Streamlit. The Claude client is passed in, so tests use a fake one."""
import base64
import hashlib
import io
import json
import os
import shutil
from datetime import datetime

from pydantic import ValidationError

import flashcards
from conversation import FALLBACK_BETA, MODEL, anthropic

from . import prompt
from .schemas import (RAW_DIR, STAGED_DIR, Artifact, ExtractedObservation, Extraction, Extractor,
                      Observation, ObservationFile)

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPILED_FILE = os.path.join(ROOT, "data", "compiled", "lesson_observations.json")

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}
UNSUPPORTED_HINT = {".heic": "HEIC is not supported: export it as PNG or JPEG first "
                             "(on a Mac: sips -s format png photo.heic --out photo.png)."}
# Sent as-is below these; larger images are scaled down first (the original
# file is what gets hashed and kept).
MAX_IMAGE_BYTES = 3_500_000
MAX_IMAGE_SIDE = 2400
# Observation types that become flashcards; corrections become drill items
# and rule notes are kept in the compiled file for later use.
CARD_TYPES = ("vocab", "expression", "example")


class IngestError(Exception):
    """This image could not be read; the message says why."""


def staged_dir(root=ROOT):
    return os.path.join(root, STAGED_DIR)


def raw_dir(root=ROOT):
    return os.path.join(root, RAW_DIR)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_images(paths):
    """Files and folders -> (supported image paths, [(path, why not)])."""
    found, skipped = [], []
    for path in paths:
        if os.path.isdir(path):
            names = sorted(os.path.join(path, n) for n in os.listdir(path) if not n.startswith("."))
            names = [n for n in names if os.path.isfile(n)]
        elif os.path.isfile(path):
            names = [path]
        else:
            skipped.append((path, "no such file or folder"))
            continue
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext in MEDIA_TYPES:
                found.append(name)
            elif ext in UNSUPPORTED_HINT:
                skipped.append((name, UNSUPPORTED_HINT[ext]))
            elif os.path.isfile(path):  # named explicitly, so say why it was left out
                skipped.append((name, f"not an image this script reads ({', '.join(sorted(MEDIA_TYPES))})"))
    return found, skipped


def load_staged(directory=None):
    """Every staged ObservationFile, by file name order. A file that no
    longer matches the schema is an error worth stopping for."""
    directory = directory or staged_dir()
    files = []
    if os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            if name.endswith(".json"):
                with open(os.path.join(directory, name), encoding="utf-8") as f:
                    files.append(ObservationFile.model_validate_json(f.read()))
    return files


def save_staged(obs_file, directory=None):
    directory = directory or staged_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, obs_file.filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obs_file.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n")
    return path


def prepare_image(path):
    """(media type, bytes) to send: the file itself when it is small enough,
    otherwise a scaled-down copy."""
    media_type = MEDIA_TYPES[os.path.splitext(path)[1].lower()]
    with open(path, "rb") as f:
        data = f.read()
    try:
        from PIL import Image
    except ImportError:
        if len(data) > MAX_IMAGE_BYTES:
            raise IngestError("the image is large and Pillow is not installed to scale it down (pip install pillow)")
        return media_type, data
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as e:
        raise IngestError(f"not a readable image: {e}") from e
    if len(data) <= MAX_IMAGE_BYTES and max(image.size) <= MAX_IMAGE_SIDE:
        return media_type, data
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=90)
    return "image/jpeg", out.getvalue()


def extract(client, media_type, data, model=MODEL, lesson=None, kind=None):
    """One vision call. Returns (kind, lesson, [ExtractedObservation],
    [why an observation was dropped]). Raises IngestError when there is no
    usable reply."""
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=prompt.system_prompt(),
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                             "data": base64.standard_b64encode(data).decode("ascii")}},
                {"type": "text", "text": prompt.user_text(lesson, kind)},
            ]}],
            output_config={"format": {"type": "json_schema", "schema": anthropic.transform_schema(Extraction)}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise IngestError("the Claude API key is not valid (check ANTHROPIC_API_KEY)") from e
    except anthropic.APIError as e:
        raise IngestError(f"Claude API error: {e}") from e
    except TypeError as e:  # the SDK found no credentials at all
        raise IngestError(f"no Claude API credentials found (set ANTHROPIC_API_KEY): {e}") from e
    if response.stop_reason == "refusal":
        raise IngestError("Claude declined to read this image")
    if response.stop_reason == "max_tokens":
        raise IngestError("the reply was cut off (too much on one screenshot?): crop it into parts")
    text = next((b.text for b in response.content if b.type == "text"), None)
    try:
        reply = json.loads(text)
        raw_observations = list(reply["observations"])
    except (TypeError, ValueError, KeyError) as e:
        raise IngestError(f"the reply was not the expected JSON: {e}") from e
    observations, dropped = [], []
    for raw in raw_observations:
        try:
            observations.append(ExtractedObservation.model_validate(raw))
        except ValidationError as e:
            first = e.errors()[0]
            what = raw.get("spanish") or raw.get("verbatim") if isinstance(raw, dict) else raw
            dropped.append(f"{str(what)[:50]!r}: {first['msg']}")
    return reply.get("kind"), reply.get("lesson"), observations, dropped


def known_items(staged, skip_artifact=None):
    """match key -> what already has it (a flashcard id or an observation id),
    for duplicate detection: every card the app already has, then every
    staged observation that isn't rejected or itself a duplicate."""
    known = {}
    for card in flashcards.load_cards():
        if card["deck"] == flashcards.LESSON_DECK[0]:
            continue  # compiled from these very observations
        for key in flashcards._match_keys(card["spanish"]):
            known.setdefault(key, card["id"])
    for obs_file in staged:
        if obs_file.artifact.sha256 == skip_artifact:
            continue
        for o in obs_file.observations:
            if o.status in ("pending", "approved") and o.type in CARD_TYPES:
                for key in flashcards._match_keys(o.spanish):
                    known.setdefault(key, o.id)
    return known


def stage(artifact, observations, known):
    """Give observations their ids and mark the ones the app already has."""
    staged = []
    for n, o in enumerate(observations, 1):
        oid = f"{artifact.short_id}-{n}"
        duplicate_of = None
        if o.type in CARD_TYPES:
            keys = flashcards._match_keys(o.spanish)
            duplicate_of = next((known[k] for k in keys if k in known), None)
            if duplicate_of is None:
                known.update({k: oid for k in keys})  # a repeat later in the same screenshot
        staged.append(Observation(**o.model_dump(), id=oid, artifact_id=artifact.sha256,
                                  status="duplicate" if duplicate_of else "pending", duplicate_of=duplicate_of))
    return ObservationFile(artifact=artifact, observations=staged)


def plan(path, directory=None, force=False, discard_reviews=False):
    """What `run` would do with this image: ("new" | "cached" | "reread" |
    "blocked", sha256, reason)."""
    directory = directory or staged_dir()
    sha = sha256_file(path)
    existing = os.path.join(directory, f"{sha[:12]}.json")
    if not os.path.exists(existing):
        return "new", sha, ""
    with open(existing, encoding="utf-8") as f:
        old = ObservationFile.model_validate_json(f.read())
    reviewed = sum(1 for o in old.observations if o.reviewed_at or o.status in ("approved", "rejected"))
    outdated = old.artifact.extractor.prompt_version != prompt.PROMPT_VERSION
    if not force and not outdated:
        return "cached", sha, "already read"
    if reviewed and not discard_reviews:
        why = "read with an older prompt, but" if outdated and not force else "it"
        return "blocked", sha, (f"{why} has {reviewed} reviewed observation(s); "
                                "add --force --discard-reviews to read it again and lose them")
    return "reread", sha, "older prompt version" if outdated and not force else "forced"


def ingest_image(client, path, lesson=None, kind=None, captured_on=None, model=MODEL, directory=None,
                 raw=None, copy=True, now=None):
    """Read one image and write its staged file. Returns (ObservationFile, dropped)."""
    directory = directory or staged_dir()
    sha = sha256_file(path)
    media_type, data = prepare_image(path)
    seen_kind, seen_lesson, observations, dropped = extract(client, media_type, data, model, lesson, kind)
    try:
        artifact = Artifact(
            sha256=sha, filename=os.path.basename(path), kind=kind or seen_kind or "other",
            lesson=lesson or seen_lesson, captured_on=captured_on, ingested_at=now or datetime.now().replace(microsecond=0),
            extractor=Extractor(model=model, prompt_version=prompt.PROMPT_VERSION))
    except ValidationError:
        # The model's own reading of kind/lesson was off: keep the observations.
        artifact = Artifact(
            sha256=sha, filename=os.path.basename(path), kind=kind or "other", lesson=lesson,
            captured_on=captured_on, ingested_at=now or datetime.now().replace(microsecond=0),
            extractor=Extractor(model=model, prompt_version=prompt.PROMPT_VERSION))
    obs_file = stage(artifact, observations, known_items(load_staged(directory), skip_artifact=sha))
    save_staged(obs_file, directory)
    if copy:
        raw = raw or raw_dir()
        os.makedirs(raw, exist_ok=True)
        target = os.path.join(raw, artifact.short_id + os.path.splitext(path)[1].lower())
        if os.path.abspath(target) != os.path.abspath(path):
            shutil.copyfile(path, target)
    return obs_file, dropped


# --- review -----------------------------------------------------------------------

EDITABLE = ("spanish", "english", "note", "wrong", "right", "why")


def decide(obs_file, observation_id, status, now=None, **edits):
    """Set one observation's status (and optionally edit its text), returning
    the updated file. Edits are validated like everything else."""
    updated = []
    for o in obs_file.observations:
        if o.id == observation_id:
            data = o.model_dump()
            for field, value in edits.items():
                if field not in EDITABLE:
                    raise ValueError(f"{field!r} can't be edited here")
                value = value.strip() or None
                if field in ("wrong", "right", "why"):
                    if data.get("correction") is None:
                        raise ValueError("only a correction has wrong / right / why")
                    data["correction"][field] = value
                else:
                    data[field] = value
            data.update(status=status, reviewed_at=now or datetime.now().replace(microsecond=0))
            if status != "duplicate":
                data["duplicate_of"] = None
            o = Observation.model_validate(data)
        updated.append(o)
    return ObservationFile(schema_version=obs_file.schema_version, artifact=obs_file.artifact, observations=updated)


def approve_high(obs_file, now=None):
    """Approve every pending, high-confidence vocabulary item and expression.
    Corrections and anything uncertain are left for a person to look at."""
    count = 0
    for o in list(obs_file.observations):
        if o.status == "pending" and o.confidence == "high" and o.type in ("vocab", "expression"):
            obs_file = decide(obs_file, o.id, "approved", now=now)
            count += 1
    return obs_file, count


def status_rows(staged):
    """One row per screenshot: (short id, lesson, file name, {status: count})."""
    rows = []
    for obs_file in staged:
        counts = {}
        for o in obs_file.observations:
            counts[o.status] = counts.get(o.status, 0) + 1
        rows.append((obs_file.artifact.short_id, obs_file.artifact.lesson or "-", obs_file.artifact.filename, counts))
    return rows


# --- compile ----------------------------------------------------------------------

def _lesson_sort(lesson):
    return flashcards.lesson_number(lesson) if lesson else float("inf")


def compile_observations(staged):
    """Approved observations as the study data the app reads. Deterministic:
    the same staged files always give the same output, so its diff shows
    exactly what a review changed."""
    cards, corrections, notes = [], [], []
    for obs_file in staged:
        lesson = obs_file.artifact.lesson
        for o in obs_file.observations:
            if o.status != "approved":
                continue
            base = {"id": o.id, "lesson": lesson, "concept_ids": o.concept_ids}
            if o.type == "correction":
                corrections.append({**base, "wrong": o.correction.wrong, "right": o.correction.right,
                                    "why": o.correction.why or "", "english": o.english or "",
                                    "error_tags": o.error_tags})
            elif o.type == "rule_note":
                notes.append({**base, "spanish": o.spanish, "english": o.english or ""})
            elif o.english:  # a card needs both sides
                cards.append({**base, "type": o.type, "spanish": o.spanish, "english": o.english,
                              "note": o.note or ""})
    order = lambda x: (_lesson_sort(x["lesson"]), x["id"])  # noqa: E731
    return {
        "_meta": {"generated_by": "python scripts/ingest.py compile",
                  "source": "approved observations in data/observations/staged/",
                  "notes": "Do not edit by hand: change the observations and compile again."},
        "cards": sorted(cards, key=order),
        "corrections": sorted(corrections, key=order),
        "rule_notes": sorted(notes, key=order),
    }


def write_compiled(compiled, path=None):
    path = path or COMPILED_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(compiled, ensure_ascii=False, indent=2) + "\n"
    changed = True
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            changed = f.read() != text
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return changed
