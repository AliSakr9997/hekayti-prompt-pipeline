"""Local, file-backed production records for reproducible story experiments.

This module deliberately has no provider or database dependency. It supplies
the durable records and deterministic checks that sit around manual or
provider-backed generation.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


class Provenance(str, Enum):
    USER_CONFIRMED = "user_confirmed"
    REFERENCE_DERIVED = "reference_derived"
    AI_PROPOSED = "ai_proposed"
    SYSTEM_DEFAULT = "system_default"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending_approval"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SceneStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    GENERATING = "generating"
    GENERATED = "generated"
    VALIDATING = "validating"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    FAILED = "failed"
    REPAIR_REQUIRED = "repair_required"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


LEGAL_TRANSITIONS: Mapping[SceneStatus, frozenset[SceneStatus]] = {
    SceneStatus.PLANNED: frozenset({SceneStatus.READY, SceneStatus.SUPERSEDED}),
    SceneStatus.READY: frozenset({SceneStatus.GENERATING, SceneStatus.SUPERSEDED}),
    SceneStatus.GENERATING: frozenset({SceneStatus.GENERATED, SceneStatus.FAILED}),
    SceneStatus.GENERATED: frozenset({SceneStatus.VALIDATING, SceneStatus.SUPERSEDED}),
    SceneStatus.VALIDATING: frozenset({
        SceneStatus.APPROVED, SceneStatus.REVIEW_REQUIRED,
        SceneStatus.REPAIR_REQUIRED, SceneStatus.FAILED,
    }),
    SceneStatus.REVIEW_REQUIRED: frozenset({SceneStatus.APPROVED, SceneStatus.REJECTED}),
    SceneStatus.REPAIR_REQUIRED: frozenset({SceneStatus.READY, SceneStatus.REJECTED}),
    SceneStatus.FAILED: frozenset({SceneStatus.READY, SceneStatus.SUPERSEDED}),
    SceneStatus.APPROVED: frozenset({SceneStatus.SUPERSEDED}),
    SceneStatus.REJECTED: frozenset({SceneStatus.READY, SceneStatus.SUPERSEDED}),
    SceneStatus.SUPERSEDED: frozenset(),
}


def _now() -> float:
    return time.time()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def story_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Attribute:
    value: str
    provenance: Provenance
    locked: bool = False


@dataclass(frozen=True)
class CharacterVersion:
    character_id: str
    story_id: str
    display_name: str
    canonical_name: str
    identity_attributes: tuple[Attribute, ...] = ()
    wardrobe: tuple[Attribute, ...] = ()
    personality_traits: tuple[Attribute, ...] = ()
    unknown_attributes: tuple[str, ...] = ()
    proposed_attributes: tuple[Attribute, ...] = ()
    reference_assets: tuple[dict[str, Any], ...] = ()
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    profile_version: int = 1
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


class CharacterStore:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, character_id: str, version: int) -> Path:
        return self.root / "characters" / character_id / f"v{version}.json"

    def save(self, profile: CharacterVersion) -> CharacterVersion:
        _write(self._path(profile.character_id, profile.profile_version), _json(profile))
        return profile

    def create(self, profile: CharacterVersion) -> CharacterVersion:
        if profile.profile_version != 1 or self._path(profile.character_id, 1).exists():
            raise ValueError("character already exists; create a new version")
        return self.save(profile)

    def get(self, character_id: str, version: int | None = None) -> CharacterVersion:
        directory = self.root / "characters" / character_id
        if version is None:
            versions = sorted(directory.glob("v*.json"), key=lambda p: int(p.stem[1:]))
            if not versions:
                raise FileNotFoundError(character_id)
            path = versions[-1]
        else:
            path = self._path(character_id, version)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return _profile(_read(path))

    def approve(self, character_id: str, version: int | None = None) -> CharacterVersion:
        profile = self.get(character_id, version)
        approved = CharacterVersion(**{
            **asdict(profile),
            "approval_status": ApprovalStatus.APPROVED,
            "updated_at": _now(),
        })
        return self.save(approved)

    def new_version(self, profile: CharacterVersion, **changes: Any) -> CharacterVersion:
        current = self.get(profile.character_id)
        next_version = current.profile_version + 1
        updated = CharacterVersion(**{
            **asdict(current),
            **changes,
            "profile_version": next_version,
            "approval_status": ApprovalStatus.DRAFT,
            "created_at": _now(),
            "updated_at": _now(),
        })
        return self.save(updated)


@dataclass(frozen=True)
class StoryVersion:
    story_id: str
    version: int
    source_text: str
    source_hash: str
    created_at: float = field(default_factory=_now)


class StoryStore:
    def __init__(self, root: Path):
        self.root = root

    def create(self, story_id: str, source_text: str, version: int = 1) -> StoryVersion:
        if not source_text:
            raise ValueError("source_text must not be empty")
        record = StoryVersion(story_id, version, source_text, story_hash(source_text))
        _write(self.root / "stories" / story_id / f"v{version}.json", _json(record))
        return record

    def get(self, story_id: str, version: int = 1) -> StoryVersion:
        return _story(_read(self.root / "stories" / story_id / f"v{version}.json"))

    def verify(self, record: StoryVersion) -> bool:
        return record.source_hash == story_hash(record.source_text)


@dataclass(frozen=True)
class ScenePlan:
    story_id: str
    story_version: int
    scene_id: str
    scene_index: int
    source_text_exact: str
    characters_present: tuple[str, ...]
    required_actions: tuple[str, ...]
    required_props: tuple[str, ...]
    visual_direction: Mapping[str, Any]
    character_profile_versions: Mapping[str, int]
    prompt_version: str = "1"
    validation_status: str = "planned"


@dataclass(frozen=True)
class GenerationManifest:
    story_id: str
    story_version: int
    scene_id: str
    character_profile_versions: Mapping[str, int]
    provider: str
    model: str
    strategy: str
    prompt: str
    reference_assets: tuple[str, ...]
    attempt: int = 1
    status: SceneStatus = SceneStatus.PLANNED
    output_path: str | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    manifest_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def transition(self, target: SceneStatus, **changes: Any) -> "GenerationManifest":
        if target not in LEGAL_TRANSITIONS[self.status]:
            raise ValueError(f"invalid transition {self.status.value} -> {target.value}")
        return GenerationManifest(**{
            **asdict(self),
            **changes,
            "status": target,
            "started_at": _now() if target is SceneStatus.GENERATING else self.started_at,
            "completed_at": _now() if target in {SceneStatus.GENERATED, SceneStatus.FAILED} else self.completed_at,
        })


@dataclass(frozen=True)
class QACheck:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class QAResult:
    qa_run_id: str
    scene_id: str
    overall_status: str
    checks: tuple[QACheck, ...]
    review_required: bool
    recommended_action: str
    rule_version: str = "deterministic-1"


def deterministic_qa(
    manifest: GenerationManifest,
    story: StoryVersion,
    scene: ScenePlan,
    required_references: Sequence[str],
) -> QAResult:
    checks: list[QACheck] = []
    checks.append(QACheck("source_integrity", "pass" if story_hash(story.source_text) == story.source_hash else "fail",
                          "authoritative source hash matches" if story_hash(story.source_text) == story.source_hash else "source hash mismatch"))
    checks.append(QACheck("output_exists", "pass" if manifest.output_path and Path(manifest.output_path).is_file() else "fail",
                          manifest.output_path or "no output path recorded"))
    checks.append(QACheck("references_available", "pass" if all(Path(p).is_file() for p in required_references) else "fail",
                          f"{len(required_references)} required reference(s) checked"))
    checks.append(QACheck("profile_versions_recorded", "pass" if scene.character_profile_versions else "fail",
                          str(dict(scene.character_profile_versions))))
    checks.append(QACheck("scene_binding", "pass" if manifest.scene_id == scene.scene_id and manifest.story_id == scene.story_id else "fail",
                          f"{manifest.story_id}/{manifest.scene_id}"))
    failed = [check for check in checks if check.status == "fail"]
    return QAResult(
        qa_run_id=uuid.uuid4().hex,
        scene_id=scene.scene_id,
        overall_status="fail" if failed else "pass",
        checks=tuple(checks),
        review_required=bool(failed),
        recommended_action="review_required" if failed else "human_review",
    )


def _json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _attribute(value: Mapping[str, Any]) -> Attribute:
    return Attribute(value["value"], Provenance(value["provenance"]), bool(value.get("locked")))


def _profile(value: Mapping[str, Any]) -> CharacterVersion:
    return CharacterVersion(
        **{**value,
           "identity_attributes": tuple(_attribute(item) for item in value.get("identity_attributes", [])),
           "wardrobe": tuple(_attribute(item) for item in value.get("wardrobe", [])),
           "personality_traits": tuple(_attribute(item) for item in value.get("personality_traits", [])),
           "proposed_attributes": tuple(_attribute(item) for item in value.get("proposed_attributes", [])),
           "approval_status": ApprovalStatus(value["approval_status"]),
           "reference_assets": tuple(value.get("reference_assets", []))},
    )


def _story(value: Mapping[str, Any]) -> StoryVersion:
    return StoryVersion(**value)
