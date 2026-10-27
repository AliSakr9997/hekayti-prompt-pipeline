from demo.server import compile_prompt_only
from hekayti.models import OutfitMode, Wardrobe


def test_wardrobe_modes_and_costume_are_structured():
    wardrobe = Wardrobe(top="blue hoodie", mode=OutfitMode.LOCKED)
    assert wardrobe.mode is OutfitMode.LOCKED
    assert "blue hoodie" in wardrobe.describe()

    result = compile_prompt_only({
        "name": "Mina",
        "appearance": ["curly black hair", "brown eyes"],
        "wardrobe": {"top": "blue hoodie", "mode": "preferred"},
        "mandatory_costume": "astronaut suit and helmet",
        "strategy": "hybrid",
        "references": ["character-sheet", "photo-front"],
    })
    assert result["prompt_only"] is True
    assert result["sections"]["identity_lock"]
    assert result["sections"]["scene_costume_rules"]
    assert "astronaut suit and helmet" in result["positive"]
    assert result["reference_ids"] == ("character-sheet", "photo-front")
