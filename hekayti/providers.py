"""Provider-neutral request and configuration types; no provider behavior is assumed."""

from dataclasses import dataclass, field
from typing import Mapping

from .models import ReferenceAsset, Strategy


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    model: str
    timeout_seconds: float = 60.0
    extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_name.strip() or not self.model.strip():
            raise ValueError("provider_name and model are required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    negative_prompt: str = ""
    references: tuple[ReferenceAsset, ...] = ()
    strategy: Strategy = Strategy.HYBRID
    width: int = 1024
    height: int = 1024
    seed: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt is required")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        object.__setattr__(self, "strategy", Strategy(self.strategy))

