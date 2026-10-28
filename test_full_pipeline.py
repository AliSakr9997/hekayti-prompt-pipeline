"""
Unit and Integration Tests for Hekayti Full Pipeline:
User Input -> Story Generation (Reem Task 2) -> Image & Scene Prompt Studio
"""

import sys
import os
from pathlib import Path
import pytest

# Ensure root is in path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEPLOY_DIR = ROOT_DIR / "image-deploy"
if str(DEPLOY_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOY_DIR))

from hekayti.story_generator import (
    StoryGenerator,
    make_story_input,
    validate_story,
    generate_fallback_story
)
from prompt_studio_engine import (
    PromptStudioEngine,
    FullPipelineRequest,
    story_dict_to_story_input
)


def test_story_generator_egyptian_arabic():
    """Verify story generation in Egyptian Arabic satisfies schema and character design."""
    inp = make_story_input(
        name="آدم",
        age=7,
        language="egyptian_arabic",
        interests=["الحشرات", "التصوير"],
        story_goal="تنمية الصبر والتركيز من خلال ملاحظة التفاصيل الصغيرة",
        story_type="قصة اكتشاف",
        page_count=5,
        additional_characters=[{"name": "المعلمة هدى", "role": "معلمة العلوم"}],
        dedication="إلى آدم، المستكشف الصغير",
        gender="boy"
    )
    story = generate_fallback_story(inp)
    validate_story(story, inp)

    assert story["title"]
    assert len(story["character_designs"]) == 2
    assert story["character_designs"][0]["name"] == "آدم"
    assert len(story["pages"]) == 5
    for p in story["pages"]:
        assert p["page"] in range(1, 6)
        assert p["scene_title"]
        assert p["text"]
        assert p["image_description"]
        assert len(p["character_reference_ids"]) >= 1


def test_story_generator_simplified_fusha():
    """Verify story generation in Simplified Fusha satisfies schema and character design."""
    inp = make_story_input(
        name="نور",
        age=10,
        language="simplified_fusha",
        interests=["تصميم الأزياء", "الخياطة"],
        story_goal="تقبل الأخطاء والتعلم من المحاولة",
        story_type="قصة عن التصميم والتعلم",
        page_count=6,
        additional_characters=[{"name": "الجدة سلمى", "role": "خياطة ماهرة"}],
        dedication="إلى نور، صاحبة الأفكار الجميلة",
        gender="girl"
    )
    story = generate_fallback_story(inp)
    validate_story(story, inp)

    assert "نور" in story["title"] or "الأزياء" in story["title"] or "الخياطة" in story["title"]
    assert len(story["pages"]) == 6
    assert story["character_designs"][0]["character_id"]
    assert "char_support_01" in [c["character_id"] for c in story["character_designs"]]


def test_story_generator_english():
    """Verify story generation in English satisfies schema."""
    inp = make_story_input(
        name="Adam",
        age=4,
        language="english",
        interests=["football", "sports"],
        story_goal="building confidence to join team",
        story_type="friendship story",
        page_count=4,
        additional_characters=[{"name": "Coach Sam", "role": "coach"}],
        gender="boy"
    )
    story = generate_fallback_story(inp)
    validate_story(story, inp)

    assert len(story["pages"]) == 4
    assert "Adam" in story["title"]
    assert "Coach Sam" in [c["name"] for c in story["character_designs"]]


def test_bridge_story_to_prompt_input():
    """Verify story_dict_to_story_input accurately converts story JSON to PromptStudio StoryInput."""
    inp = make_story_input(
        name="كريم",
        age=6,
        language="simplified_fusha",
        interests=["الفضاء", "النجوم"],
        story_goal="استكشاف الكون",
        story_type="مغامرة فضاء",
        page_count=3,
        gender="boy"
    )
    story = generate_fallback_story(inp)

    story_input_obj = story_dict_to_story_input(
        story_data=story,
        art_style="Disney Pixar 3D animated illustration",
        target_model="qwen-image-2.0-pro",
        user_physical_identity="شعر أسود كيرلي مموج، عينان بنيتان دافئتان",
        user_canonical_wardrobe="معطف أصفر واقٍ من المطر مع حذاء أحمر",
        intended_age="6",
        gender="boy"
    )

    assert story_input_obj.title == story["title"]
    assert len(story_input_obj.characters) >= 1
    protagonist = story_input_obj.characters[0]
    assert protagonist.display_name == "كريم"
    assert protagonist.canonical_clothing == "معطف أصفر واقٍ من المطر مع حذاء أحمر"
    assert "كيرلي" in protagonist.hair_details
    assert len(story_input_obj.prestructured_scenes) == 3


def test_full_pipeline_end_to_end(tmp_path):
    """
    Test complete full pipeline:
    User Input -> Story Generation -> Prompt Pack Generation -> ZIP Export.
    """
    engine = PromptStudioEngine(output_dir=tmp_path)

    pipeline_req = FullPipelineRequest(
        child_name="آدم",
        child_age=7,
        child_gender="boy",
        language="egyptian_arabic",
        interests=["الحشرات", "التصوير"],
        story_goal="تنمية الصبر والتركيز",
        story_type="قصة اكتشاف",
        page_count=4,
        additional_characters=[{"name": "المعلمة هدى", "role": "معلمة العلوم"}],
        dedication="إلى آدم البطل",
        art_style="Disney Pixar 3D animated illustration, warm vibrant colors",
        target_image_model="qwen-image-2.0-pro",
        provider_preference="fallback"
    )

    result = engine.generate_full_pipeline(pipeline_req)

    assert result["success"] is True
    assert "story_id" in result
    assert "story" in result
    assert "prompt_pack" in result
    assert "zip_download_url" in result

    # Check Story JSON structure
    story = result["story"]
    assert story["title"]
    assert len(story["pages"]) == 4
    assert all(page["image_prompt"] for page in story["pages"])
    assert all("image_prompts" in page for page in story["pages"])
    assert len(result["scenes"]) == 4
    assert all(scene["content"] for scene in result["scenes"])
    assert all("Reference images are available" in scene["image_prompt"] for scene in result["scenes"])

    # Check Prompt Pack structure
    pack = result["prompt_pack"]
    assert pack["manifest"]["title"] == story["title"]
    assert len(pack["scene_prompts"]) == 4
    
    # Check that scene prompts exist and include character & setting anchors
    for sc in pack["scene_prompts"]:
        assert sc["scene_id"]
        assert sc["page_number"]
        assert sc["exact_arabic_text"]
        assert "prompt_workflow_a" in sc
        assert "prompt_workflow_b" in sc
        assert "prompt_workflow_c" in sc
        assert "negative_prompt" in sc

    # Check that Cover Prompt was generated
    assert "cover_prompt" in pack["cover_prompt"]
    assert "negative_prompt" in pack["cover_prompt"]
    assert len(pack["cover_prompt"]["cover_prompt"]) > 20

    # Check that ZIP was created on disk
    zip_path = tmp_path / f"{result['story_id']}_prompt_pack.zip"
    assert zip_path.exists()
    assert zip_path.stat().st_size > 0


def test_full_pipeline_accepts_user_story_text(tmp_path):
    """A supplied story is preserved and enriched with one prompt per scene."""
    engine = PromptStudioEngine(output_dir=tmp_path)
    supplied_text = (
        "ذهبت مينا إلى الحديقة ورأت فراشة جميلة. "
        "جلست بهدوء ترسم الزهور وتتعلم أن الصبر يساعدها على ملاحظة التفاصيل."
    )
    request = FullPipelineRequest(
        child_name="مينا",
        child_age=6,
        child_gender="girl",
        page_count=2,
        interests=["الرسم"],
        story_text=supplied_text,
        physical_identity="شعر أسود كيرلي ووجه مستدير",
        canonical_wardrobe="معطف أصفر وحذاء أحمر",
        provider_preference="fallback",
    )

    result = engine.generate_full_pipeline(request)

    assert result["provider_used"] == "user_story_text"
    assert len(result["scenes"]) == 2
    assert "".join(scene["content"] for scene in result["scenes"]).replace(" ", "") == supplied_text.replace(" ", "")
    assert all(scene["image_prompt"] for scene in result["scenes"])


def test_two_character_reference_mapping_and_unified_prompt(tmp_path):
    """
    Verify prompt compilation with 2 characters (e.g. Karim and Teacher):
    - Characters faces are NOT described textually.
    - AI is told to use their referenced imported images by index:
      'Karim is the first image [Image 1], and Teacher is the second image [Image 2]'.
    - Unified prompt: contains both positive prompt and negative prompt together in one string.
    - Image aspect ratio is 9:16 vertical.
    """
    engine = PromptStudioEngine(output_dir=tmp_path)
    request = FullPipelineRequest(
        child_name="كريم / Karim",
        child_age=6,
        child_gender="boy",
        page_count=3,
        interests=["الفضاء", "النجوم"],
        story_goal="الاستكشاف والتعلم في المدرسة",
        story_type="مغامرة مدرسية فضائية",
        additional_characters=[{"name": "معلمة العلوم / Teacher Huda", "role": "معلمة تشجع كريم"}],
        provider_preference="fallback",
    )

    result = engine.generate_full_pipeline(request)
    assert result["success"] is True
    scenes = result["scenes"]
    assert len(scenes) == 3

    for sc in scenes:
        prompt = sc["image_prompt"]
        # 1. Unified prompt: prompt + negative in ONE string
        assert "Negative prompt:" in prompt, "Prompt must include negative prompt as one combined prompt"

        # 2. Characters referenced by index
        assert "Karim is the first image [Image 1]" in prompt
        assert "Teacher Huda is the second image [Image 2]" in prompt
        assert "Use their referenced imported images" in prompt

        # 3. No facial descriptions
        assert "dark-brown eyes" not in prompt
        assert "eye shape" not in prompt
        assert "skin tone" not in prompt

        # 4. 9:16 vertical ratio
        assert "9:16" in prompt
        assert "vertical" in prompt.lower()

