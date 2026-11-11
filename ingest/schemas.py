"""Data contracts for turning lesson screenshots into study material.

    screenshot --(hash)--> Artifact
               --(Claude vision)--> ExtractedObservation, ...   what the model returns
               --(ids, status)--> Observation, ...              what is stored
    one ObservationFile per screenshot in data/observations/staged/<sha12>.json

The raw image stays out of git (data/artifacts/raw/); the Artifact record and
its observations are what get committed. An observation is the raw unit
("the tutor corrected X to Y"); turning approved observations into decks and
drill items is a later, separate step.

ExtractedObservation is deliberately plain (enums, strings, lists, no numeric
or pattern constraints) so its JSON schema can be given to Claude as a
structured-output format unchanged. The rules a schema can't express are
checked by the validators here after the reply is parsed."""
import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import concepts

SCHEMA_VERSION = 1
STAGED_DIR = "data/observations/staged"
RAW_DIR = "data/artifacts/raw"  # git-ignored

ArtifactKind = Literal["whiteboard", "chat", "exercise", "notes", "other"]
ObservationType = Literal["vocab", "expression", "correction", "example", "rule_note"]
# Where on the screenshot it was. Interface noise (buttons, timestamps, names)
# is never an observation: the extractor is told to leave it out.
Region = Literal["tutor_annotation", "board", "exercise", "learner_text"]
Confidence = Literal["high", "medium", "low"]
Status = Literal["pending", "approved", "rejected", "duplicate"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Extractor(_Model):
    model: str
    prompt_version: str


class Artifact(_Model):
    """One screenshot. Its sha256 is its identity, so the same image is never ingested twice."""
    sha256: str
    filename: str = Field(description="Original file name, for the human; the hash is the key.")
    kind: ArtifactKind
    lesson: Optional[str] = Field(default=None, description="'L113': same convention as first_seen in the vocabulary reference.")
    captured_on: Optional[date] = None
    ingested_at: datetime
    extractor: Extractor

    @field_validator("sha256")
    @classmethod
    def _sha(cls, v):
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return v

    @field_validator("lesson")
    @classmethod
    def _lesson(cls, v):
        if v is not None and not re.fullmatch(r"L\d+(\.\d+)?", v):
            raise ValueError("lesson looks like 'L113'")
        return v

    @property
    def short_id(self):
        return self.sha256[:12]


class Correction(_Model):
    """The tutor's fix: what was said, what to say, and why."""
    wrong: str
    right: str
    why: Optional[str] = None


class ExtractedObservation(_Model):
    """One thing worth learning from a screenshot, as the model reports it."""
    type: ObservationType
    region: Region
    verbatim: str = Field(description="Exactly as written on the screenshot, mistakes included.")
    spanish: str = Field(description="The Spanish to learn, with spelling and accents corrected.")
    english: Optional[str] = Field(default=None, description="Gloss or translation.")
    correction: Optional[Correction] = Field(default=None, description="Required when type is 'correction'.")
    concept_ids: list[str] = Field(default_factory=list, description="Grammar/vocab concepts from data/concepts.json.")
    error_tags: list[str] = Field(default_factory=list, description="Kinds of mistake from data/concepts.json; corrections only.")
    confidence: Confidence
    note: Optional[str] = Field(default=None, description="Anything the reviewer should know, e.g. hard-to-read handwriting.")

    @field_validator("verbatim", "spanish")
    @classmethod
    def _not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("concept_ids")
    @classmethod
    def _known_concepts(cls, v):
        known = set(concepts.ids("grammar")) | set(concepts.ids("vocab"))
        unknown = [c for c in v if c not in known]
        if unknown:
            raise ValueError(f"not grammar/vocab concepts in data/concepts.json: {unknown}")
        return v

    @field_validator("error_tags")
    @classmethod
    def _known_tags(cls, v):
        unknown = [t for t in v if t not in concepts.error_tags()]
        if unknown:
            raise ValueError(f"not error tags in data/concepts.json: {unknown}")
        return v

    @model_validator(mode="after")
    def _correction_rules(self):
        if self.type == "correction" and self.correction is None:
            raise ValueError("a 'correction' needs its wrong/right pair")
        if self.type != "correction" and (self.correction is not None or self.error_tags):
            raise ValueError("only a 'correction' has a wrong/right pair or error tags")
        if self.correction and self.correction.wrong.strip() == self.correction.right.strip():
            raise ValueError("correction: wrong and right are the same")
        return self


class Extraction(_Model):
    """The whole reply for one screenshot (the structured-output format)."""
    kind: ArtifactKind
    lesson: Optional[str] = Field(default=None, description="Lesson number if the screenshot shows one, as 'L113'.")
    observations: list[ExtractedObservation]


class Observation(ExtractedObservation):
    """An extracted observation, stored: with an id, its source and a review status."""
    id: str = Field(description="'<artifact sha256, first 12>-<n>'")
    artifact_id: str = Field(description="sha256 of the Artifact it came from.")
    status: Status = "pending"
    duplicate_of: Optional[str] = Field(default=None, description="What it repeats: another observation's id or an existing card's id.")
    reviewed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _status_rules(self):
        if not self.id.startswith(self.artifact_id[:12] + "-"):
            raise ValueError("id must start with the first 12 characters of artifact_id")
        if (self.status == "duplicate") != (self.duplicate_of is not None):
            raise ValueError("duplicate_of goes with status 'duplicate', and only with it")
        return self


class ObservationFile(_Model):
    """data/observations/staged/<sha12>.json: one screenshot and what was read from it.
    Re-running a screenshot rewrites its own file, so runs are repeatable."""
    schema_version: int = SCHEMA_VERSION
    artifact: Artifact
    observations: list[Observation]

    @model_validator(mode="after")
    def _consistent(self):
        ids = [o.id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("observation ids must be unique")
        if any(o.artifact_id != self.artifact.sha256 for o in self.observations):
            raise ValueError("every observation must belong to this file's artifact")
        return self

    @property
    def filename(self):
        return f"{self.artifact.short_id}.json"


def stage(artifact, extraction):
    """Extracted observations -> an ObservationFile, with ids and 'pending' status."""
    return ObservationFile(artifact=artifact, observations=[
        Observation(**o.model_dump(), id=f"{artifact.short_id}-{n}", artifact_id=artifact.sha256)
        for n, o in enumerate(extraction.observations, 1)])
