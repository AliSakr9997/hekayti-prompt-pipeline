"""Deterministic prompt construction with explicit reference ordering."""

from dataclasses import dataclass

from .models import CharacterProfile, Scene, Strategy, ValidationError


@dataclass(frozen=True)
class CompiledPrompt:
    positive: str
    negative: str
    reference_ids: tuple[str, ...]
    strategy: Strategy
    sections: dict[str, str] | None = None


class PromptCompiler:
    """Compile the same inputs to byte-for-byte stable prompt text."""

    def __init__(self, strategy: Strategy = Strategy.HYBRID) -> None:
        self.strategy = Strategy(strategy)

    def compile(self, scene: Scene, characters: dict[str, CharacterProfile]) -> CompiledPrompt:
        missing = [cid for cid in scene.character_ids if cid not in characters]
        if missing:
            raise ValidationError(f"missing characters: {', '.join(missing)}")
        selected = [characters[cid] for cid in scene.character_ids]
        states = {state.character_id: state for state in scene.character_states}
        character_parts = []
        refs: list[str] = []
        for character in selected:
            state = states.get(character.id)
            state_text = ""
            if state:
                state_text = (
                    f"; action: {state.action}"
                    + (f"; pose: {state.pose}" if state.pose else "")
                    + (f"; expression: {state.expression}" if state.expression else "")
                    + (f"; outfit: {state.outfit_override}" if state.outfit_override else "")
                    + (f"; position: {state.screen_position}" if state.screen_position else "")
                )
            wardrobe = state.outfit_override if state and state.outfit_override else character.wardrobe_config.describe()
            costume = state.mandatory_costume if state and state.mandatory_costume else ""
            character_parts.append(
                f"{character.name} ({character.age}); appearance: {', '.join(character.appearance)}"
                + (f"; wardrobe: {wardrobe}" if wardrobe else "")
                + (f"; mandatory scene costume: {costume}" if costume else "")
                + state_text
            )
            refs.extend(self._select_references(character))
        refs.extend(scene.reference_asset_ids)
        # Preserve declared order while removing duplicates.
        reference_ids = tuple(dict.fromkeys(refs))
        context = " ".join(part for part in (scene.setting, scene.action, scene.camera,
                                               scene.lighting, scene.palette) if part)
        strategy_text = {
            Strategy.SHEET: "prioritize the character reference sheet for identity",
            Strategy.PHOTOS: "prioritize the character photo references for identity",
            Strategy.HYBRID: "use the reference sheet and photos together for identity",
        }[self.strategy]
        identity = "; ".join(f"{character.name}: {', '.join(character.appearance)}" for character in selected)
        outfit = "; ".join(character_parts)
        positive = (
            f"{scene.description}. {context}. "
            + (f"Original Arabic scene text: {scene.scene_text_ar}. " if scene.scene_text_ar else "")
            + (f"Props: {', '.join(scene.props)}. " if scene.props else "")
            + (f"Mood: {scene.mood}. " if scene.mood else "")
            + f"Characters: {'; '.join(character_parts)}. {strategy_text}."
        )
        negative_items = list(
            dict.fromkeys(item for character in selected for item in character.negative_constraints)
        )
        negative_items.extend(
            item for item in scene.negative_prompt if item not in negative_items
        )
        negative = ", ".join(negative_items)
        sections = {
            "identity_lock": f"Stable identity only; never change face, skin tone, eye spacing, hairline, hairstyle, or distinctive features. {identity}",
            "appearance": "; ".join(character_parts),
            "outfit": outfit,
            "scene_costume_rules": "Mandatory scene costume overrides preferred/automatic wardrobe; locked wardrobe wins unless safety or explicit story role requires the costume. Preserve identity in every case.",
            "reference_roles": strategy_text,
            "illustration_style": "Warm colorful children's storybook illustration in a gentle editorial watercolor style.",
            "negative_constraints": negative,
        }
        return CompiledPrompt(positive.strip(), negative, reference_ids, self.strategy, sections)

    def _select_references(self, character: CharacterProfile) -> list[str]:
        """Select references by declared role without inventing or duplicating assets."""
        assets = list(character.reference_assets)
        if self.strategy is Strategy.SHEET:
            selected = [asset for asset in assets if asset.kind == "sheet"]
        elif self.strategy is Strategy.PHOTOS:
            selected = [asset for asset in assets if asset.kind == "photo"]
        else:
            selected = [
                asset for asset in assets
                if asset.kind in {"sheet", "photo"} or asset.role == "character"
            ]
        return [asset.id for asset in selected]
