"""Typed domain models and validation for character-consistent image generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class ValidationError(ValueError):
    """Raised when a pipeline model is invalid."""


class Strategy(str, Enum):
    SHEET = "sheet"
    PHOTOS = "photos"
    HYBRID = "hybrid"


class OutfitMode(str, Enum):
    LOCKED = "locked"
    PREFERRED = "preferred"
    AUTOMATIC = "automatic"


@dataclass(frozen=True)
class Wardrobe:
    """Selectable clothing, kept separate from stable character identity."""

    top: str = ""
    outerwear: str = ""
    bottom: str = ""
    dress: str = ""
    shoes: str = ""
    accessories: tuple[str, ...] = ()
    mode: OutfitMode = OutfitMode.PREFERRED

    def __post_init__(self) -> None:
        for name, value in (("top", self.top), ("outerwear", self.outerwear), ("bottom", self.bottom), ("dress", self.dress), ("shoes", self.shoes)):
            if value and (not isinstance(value, str) or not value.strip()):
                raise ValidationError(f"{name} must be non-empty when provided")
        if any(not isinstance(item, str) or not item.strip() for item in self.accessories):
            raise ValidationError("accessories must contain non-empty strings")
        object.__setattr__(self, "mode", OutfitMode(self.mode))

    def describe(self) -> str:
        parts = [value for value in (self.top, self.outerwear, self.bottom, self.dress, self.shoes) if value]
        parts.extend(self.accessories)
        return ", ".join(parts) or "the approved default outfit"


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class ReferenceAsset:
    """A reference supplied to a provider, without assuming a transport format."""

    id: str
    uri: str
    kind: str = "image"
    role: str = "character"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.id, "reference id")
        _text(self.uri, "reference uri")
        _text(self.kind, "reference kind")
        _text(self.role, "reference role")


@dataclass(frozen=True)
class CharacterProfile:
    """Stable identity attributes used by prompt compilation and QA."""

    id: str
    name: str
    age: str
    appearance: tuple[str, ...]
    wardrobe: tuple[str, ...] = ()
    personality: tuple[str, ...] = ()
    negative_constraints: tuple[str, ...] = ()
    reference_assets: tuple[ReferenceAsset, ...] = ()
    tags: tuple[str, ...] = ()
    wardrobe_config: Wardrobe = field(default_factory=Wardrobe)

    def __post_init__(self) -> None:
        _text(self.id, "character id")
        _text(self.name, "character name")
        _text(self.age, "character age")
        if not self.appearance:
            raise ValidationError("appearance must contain at least one item")
        for name, values in (
            ("appearance", self.appearance),
            ("wardrobe", self.wardrobe),
            ("personality", self.personality),
            ("negative_constraints", self.negative_constraints),
            ("tags", self.tags),
        ):
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValidationError(f"{name} items must be non-empty strings")
        ids = [asset.id for asset in self.reference_assets]
        if len(ids) != len(set(ids)):
            raise ValidationError("reference asset ids must be unique")

    @classmethod
    def create(
        cls,
        *,
        id: str,
        name: str,
        age: str,
        appearance: Sequence[str],
        wardrobe: Sequence[str] = (),
        personality: Sequence[str] = (),
        negative_constraints: Sequence[str] = (),
        reference_assets: Sequence[ReferenceAsset] = (),
        tags: Sequence[str] = (),
        wardrobe_config: Wardrobe | None = None,
    ) -> "CharacterProfile":
        return cls(
            id, name, age, tuple(appearance), tuple(wardrobe), tuple(personality),
            tuple(negative_constraints), tuple(reference_assets), tuple(tags),
            wardrobe_config or Wardrobe()
        )


@dataclass(frozen=True)
class CharacterSceneState:
    """Scene-specific state kept separate from persistent character identity."""

    character_id: str
    action: str
    pose: str = ""
    expression: str = ""
    outfit_override: str | None = None
    mandatory_costume: str | None = None
    screen_position: str = ""

    def __post_init__(self) -> None:
        _text(self.character_id, "character id")
        _text(self.action, "character action")
        for name, value in (
            ("pose", self.pose),
            ("expression", self.expression),
            ("screen position", self.screen_position),
        ):
            if value and (not isinstance(value, str) or not value.strip()):
                raise ValidationError(f"{name} must be a non-empty string when provided")
        if self.outfit_override is not None:
            _text(self.outfit_override, "outfit override")
        if self.mandatory_costume is not None:
            _text(self.mandatory_costume, "mandatory costume")


@dataclass(frozen=True)
class Scene:
    """A scene description independent of any image provider."""

    id: str
    description: str
    setting: str
    action: str = ""
    camera: str = ""
    lighting: str = ""
    palette: str = ""
    aspect_ratio: str = "1:1"
    character_ids: tuple[str, ...] = ()
    reference_asset_ids: tuple[str, ...] = ()
    negative_prompt: tuple[str, ...] = ()
    scene_text_ar: str = ""
    character_states: tuple[CharacterSceneState, ...] = ()
    props: tuple[str, ...] = ()
    mood: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "scene id")
        _text(self.description, "scene description")
        _text(self.setting, "scene setting")
        _text(self.aspect_ratio, "aspect ratio")
        if not self.character_ids:
            raise ValidationError("scene must contain at least one character id")
        if len(self.character_ids) > 3:
            raise ValidationError("scene supports at most three characters")
        if any(not isinstance(item, str) or not item.strip() for item in
               (*self.character_ids, *self.reference_asset_ids, *self.negative_prompt, *self.props)):
            raise ValidationError("scene list items must be non-empty strings")
        if self.scene_text_ar and not isinstance(self.scene_text_ar, str):
            raise ValidationError("scene_text_ar must be a string")
        state_ids = tuple(state.character_id for state in self.character_states)
        if len(state_ids) != len(set(state_ids)):
            raise ValidationError("character states must have unique character ids")
        if self.character_states and set(state_ids) != set(self.character_ids):
            raise ValidationError("character states must match scene character ids")
        if self.mood and not isinstance(self.mood, str):
            raise ValidationError("mood must be a string")

    @classmethod
    def create(cls, *, id: str, description: str, setting: str,
               character_ids: Sequence[str], **kwargs: object) -> "Scene":
        states = kwargs.get("character_states", ())
        if states and not all(isinstance(state, CharacterSceneState) for state in states):
            raise ValidationError("character_states must contain CharacterSceneState values")
        return cls(id, description, setting, character_ids=tuple(character_ids), **kwargs)
