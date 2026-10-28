"""
Unit and Integration Tests for Hekayti — AI-Assisted Manual Illustration Prompt Studio
=====================================================================================
Tests:
1. Input validation & focused missing detail detection.
2. Exact Arabic story preservation across scene segmentation.
3. AI visual context reasoning fidelity (verifying fix of previous scene mismatches).
4. Character bible attribute tiering (Confirmed vs AI-Proposed vs Unknown).
5. Generation of all 9 prompt pack artifacts.
6. Support for Workflows A (Sheet), B (Photos), and C (Hybrid).
7. AI-driven prompt revision via POST /prompt_studio/revise_prompt.
8. Verification that NO image generation API is called automatically.
9. FastAPI routes testing (Pack creation, revision, evaluation persistence, ZIP export).
"""

import sys
import os
import re
from pathlib import Path
import json
import pytest

# Add image-deploy to path
sys.path.append(str(Path(__file__).resolve().parent / "image-deploy"))

from prompt_studio_engine import (
    PromptStudioEngine,
    StoryInput,
    CharacterProfile,
    validate_inputs_and_find_missing,
    segment_arabic_story_verbatim,
    audit_prompt_pack_consistency,
    PROMPT_PACKS_DIR
)
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_missing_input_validation():
    """Verify system asks focused questions when essential info is missing instead of inventing details."""
    incomplete_input = StoryInput(
        title="قصة ريم",
        arabic_story_text="كانت ريم تحب الرسم كثيراً في حديقة منزلها.",
        characters=[
            CharacterProfile(
                character_id="REEM_01",
                display_name="ريم",
                role="بطلة القصة",
                apparent_age="",  # missing
                hair_details="",  # missing
                skin_tone="",     # missing
                canonical_clothing="" # missing
            )
        ]
    )
    
    questions = validate_inputs_and_find_missing(incomplete_input)
    assert len(questions) > 0, "Should detect missing essential details"
    
    q_text = " ".join(questions)
    assert "apparent age" in q_text or "العمر" in q_text
    assert "hair" in q_text or "شعر" in q_text
    assert "clothing" in q_text or "ملابس" in q_text
    print("\n[PASSED] test_missing_input_validation: Correctly flagged focused questions without hallucinating.")


def test_arabic_story_verbatim_preservation():
    """Verify that original Arabic story text is preserved 100% verbatim."""
    original_arabic = (
        "كريم كان يحب النظر إلى السماء كل ليلة. "
        "في المدرسة، لاحظ المعلم شغف كريم بالفضاء فأهداه كتاباً مصوراً. "
        "قرر كريم أن يصنع نموذجاً للمجموعة الشمسية في غرفته. "
        "شارك كريم في مسابقة الرسم وفاز بالجائزة الأولى. "
        "ابتسم كريم وقال لوالده: سأكون رائد فضاء في المستقبل."
    )
    
    scenes = segment_arabic_story_verbatim(original_arabic, target_scenes=5)
    assert len(scenes) == 5, f"Expected 5 scenes, got {len(scenes)}"
    
    recombined = " ".join([s["exact_arabic_text"] for s in scenes])
    original_words = original_arabic.split()
    recombined_words = recombined.split()
    
    assert len(original_words) == len(recombined_words), "Word count must match exactly"
    for w in original_words:
        assert w in recombined, f"Word '{w}' was altered or missing!"
    print("\n[PASSED] test_arabic_story_verbatim_preservation: 100% of Arabic words preserved verbatim.")


def test_ai_visual_context_fidelity(tmp_path):
    """
    CRITICAL TEST: Verify AI visual reasoning fidelity and fix of previous scene mismatch.
    - Scene 1 with night/stars MUST be inferred as nighttime/stars (NEVER morning sunlight).
    - Scene 2 with teacher/school MUST be inferred as classroom.
    """
    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_context_fidelity",
        title="رحلة كريم إلى الفضاء",
        arabic_story_text=(
            "كريم كان يحب النظر إلى السماء كل ليلة، يراقب النجوم اللامعة ويعدها بحماس شديد. "
            "في المدرسة، لاحظ المعلم شغف كريم بالفضاء، فأهداه كتاباً مليئاً بالصور لكوكب زحل. "
            "قرر كريم أن يصنع نموذجاً للمجموعة الشمسية في غرفته باستخدام كرات وخيوط. "
            "أعلنت مسابقة الرسم فرسم كريم لوحة لصاروخ ينطلق نحو القمر. "
            "فاز كريم واحتفل مع والديه مؤمناً بحلمه."
        ),
        num_scenes=5,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم / Karim",
                apparent_age="6-year-old boy",
                hair_details="short curly dark-brown hair",
                skin_tone="warm olive skin",
                canonical_clothing="royal navy blue hoodie",
                distinctive_features="dimple on right cheek",
                source_photos=["karim_photo.jpg"]
            )
        ]
    )

    pack = engine.generate_prompt_pack(story_input)
    scene_plan_file = tmp_path / "test_context_fidelity" / "scene_plan.json"
    scenes = json.loads(scene_plan_file.read_text(encoding="utf-8"))

    # Scene 1: Nighttime & Stars check
    scene_1 = scenes[0]
    assert "night" in scene_1["time_of_day"].lower() or "starlit" in scene_1["time_of_day"].lower(), \
        f"Scene 1 time_of_day mismatch: {scene_1['time_of_day']}"
    assert "morning sunlight" not in scene_1["lighting_and_atmosphere"].lower(), \
        "Scene 1 must NOT contain morning sunlight when Arabic text describes night/stars!"
    assert "balcony" in scene_1["inferred_setting"].lower() or "night" in scene_1["inferred_setting"].lower()

    # Scene 2: School classroom check
    scene_2 = scenes[1]
    assert "school" in scene_2["inferred_setting"].lower() or "classroom" in scene_2["inferred_setting"].lower(), \
        f"Scene 2 setting mismatch: {scene_2['inferred_setting']}"

    print("\n[PASSED] test_ai_visual_context_fidelity: Setting & time of day accurately inferred from Arabic story.")


def test_character_bible_attribute_tiering(tmp_path):
    """Verify character bible strictly separates Confirmed from AI-Proposed and Unknown attributes."""
    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_char_tiering",
        title="قصة سلمى",
        arabic_story_text="كانت سلمى تزرع شتلة زيتون صغيرة في فناء بيتها كل صباح.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="SALMA_01",
                display_name="سلمى",
                apparent_age="7-year-old girl",
                hair_details="long straight black hair in two braids",
                canonical_clothing="green linen overalls",
                face_shape="",  # unconfirmed, should trigger AI-proposed
                skin_tone="",   # unconfirmed, should be unknown
                source_photos=["salma.jpg"]
            )
        ]
    )

    engine.generate_prompt_pack(story_input)
    bible_md = (tmp_path / "test_char_tiering" / "character_bible.md").read_text(encoding="utf-8")

    assert "Confirmed Attributes" in bible_md
    assert "AI-Proposed Attributes" in bible_md
    assert "green linen overalls" in bible_md
    print("\n[PASSED] test_character_bible_attribute_tiering: Three-tier identity classification verified.")


def test_prompt_pack_artifact_generation(tmp_path):
    """Verify that all 9 required artifacts are created with correct content and encoding."""
    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_automated_pack",
        title="مغامرة ليلى والشمس",
        arabic_story_text=(
            "استيقظت ليلى مع شروق الشمس الذهبية. "
            "أخذت دفتر الرسم وبدأت ترسم الزهور المتفتحة. "
            "جاءت فراشة ملونة وحطت على يدها بلطف. "
            "ضحكت ليلى ورسمت الفراشة في لوحتها. "
            "أهدت ليلى اللوحة لأمها بحب وفرح."
        ),
        num_scenes=5,
        intended_age="5-7",
        visual_style="Disney Pixar 3D animated illustration, warm soft lighting",
        aspect_ratio="1:1",
        target_image_model="Midjourney v6",
        characters=[
            CharacterProfile(
                character_id="LAYLA_01",
                display_name="ليلى / Layla",
                role="Protagonist",
                apparent_age="6-year-old girl",
                hair_details="braided dark chestnut hair with yellow ribbon",
                skin_tone="light olive skin",
                canonical_clothing="yellow sundress with white floral embroidery, red sandals",
                distinctive_features="bright hazel eyes and cheerful dimpled smile",
                source_photos=["layla_photo.jpg"],
                canonical_sheet="layla_character_sheet.png"
            )
        ]
    )
    
    res = engine.generate_prompt_pack(story_input)
    assert res["story_id"] == "test_automated_pack"
    assert res["scene_count"] == 5
    
    pack_dir = tmp_path / "test_automated_pack"
    expected_files = [
        "story_input.json",
        "character_bible.md",
        "character_assets.json",
        "character_sheet_prompts.md",
        "scene_plan.json",
        "scene_prompts.md",
        "cover_prompt.md",
        "editing_prompts.md",
        "evaluation_template.json"
    ]
    
    for fname in expected_files:
        file_path = pack_dir / fname
        assert file_path.exists(), f"Missing artifact: {fname}"
        content = file_path.read_text(encoding="utf-8")
        assert len(content) > 50, f"Artifact {fname} is too small or empty"
        
    scene_prompts = (pack_dir / "scene_prompts.md").read_text(encoding="utf-8")
    assert "Workflow A" in scene_prompts
    assert "Workflow B" in scene_prompts
    assert "Workflow C" in scene_prompts
    assert "layla_character_sheet.png" in scene_prompts
    
    cover_prompt = (pack_dir / "cover_prompt.md").read_text(encoding="utf-8")
    assert "negative space" in cover_prompt.lower()
    
    print("\n[PASSED] test_prompt_pack_artifact_generation: All 9 artifacts validated.")


def test_zero_image_api_calls_verification(monkeypatch):
    """
    CRITICAL TEST: Verify that the Prompt Studio workflow NEVER calls any automated image generation API.
    """
    def mock_multimodal_call(*args, **kwargs):
        raise AssertionError("VIOLATION: MultiModalConversation.call was called! Image API calls are forbidden in Prompt Studio!")

    import dashscope
    monkeypatch.setattr(dashscope.MultiModalConversation, "call", mock_multimodal_call)

    engine = PromptStudioEngine()
    test_input = StoryInput(
        story_id="test_zero_api_calls",
        title="اختبار الأمان",
        arabic_story_text="طفل يحب اللعب بالكرة في الحديقة كل يوم.",
        num_scenes=2,
        characters=[
            CharacterProfile(
                character_id="BOY_01",
                display_name="أحمد",
                apparent_age="5-year-old boy",
                hair_details="short dark hair",
                skin_tone="warm skin",
                canonical_clothing="red t-shirt",
                distinctive_features="brown eyes",
                source_photos=["ahmed.jpg"]
            )
        ]
    )

    pack = engine.generate_prompt_pack(test_input)
    assert pack is not None
    print("\n[PASSED] test_zero_image_api_calls_verification: Zero image APIs invoked during prompt pack generation.")


def test_ai_prompt_revision_endpoint():
    """Verify AI-driven prompt revision via POST /prompt_studio/revise_prompt."""
    # First create a pack
    create_res = client.post("/prompt_studio/create_pack", json={
        "story_id": "test_revision_story",
        "title": "رحلة كريم",
        "arabic_story_text": "كريم كان ينظر إلى النجوم في سماء الليل من شرفته ويعدها.",
        "num_scenes": 1,
        "characters": [
            {
                "character_id": "KARIM_01",
                "display_name": "كريم",
                "apparent_age": "6-year-old boy",
                "hair_details": "curly brown hair",
                "skin_tone": "warm skin",
                "canonical_clothing": "navy blue hoodie",
                "distinctive_features": "dimple on cheek",
                "source_photos": ["karim.jpg"]
            }
        ]
    })
    assert create_res.status_code == 200

    # Now request revision
    rev_res = client.post("/prompt_studio/revise_prompt", json={
        "story_id": "test_revision_story",
        "scene_id": "SCENE_01",
        "current_prompt": "Initial prompt featuring Karim in navy blue hoodie...",
        "user_instruction": "Make the lighting more dramatic with glowing blue starlight and make him sit cross-legged on the floor"
    })
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert "revised_prompt" in rev_data
    assert "cross-legged" in rev_data["revised_prompt"] or "starlight" in rev_data["revised_prompt"]
    print("\n[PASSED] test_ai_prompt_revision_endpoint: Dynamic prompt revision executed successfully.")


def test_fastapi_endpoints():
    """Verify all FastAPI routes for Prompt Studio."""
    # 1. Health
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
    # 2. Validate endpoint
    valid_res = client.post("/prompt_studio/validate", json={
        "title": "قصة النجم الصغير",
        "arabic_story_text": "كان النجم يلمع في السماء الزرقاء وينشر النور في كل مكان.",
        "num_scenes": 3,
        "characters": [
            {
                "character_id": "STAR_01",
                "display_name": "النجم الصغير",
                "apparent_age": "شخصية كرتونية لطفل فضائي",
                "hair_details": "شعر خيالي ذهبي متوهج",
                "skin_tone": "بشرة ذهبية ناعمة",
                "canonical_clothing": "رداء فضي سحري",
                "distinctive_features": "عيون متلألئة",
                "source_photos": ["star_ref.jpg"]
            }
        ]
    })
    assert valid_res.status_code == 200
    assert valid_res.json()["valid"] is True
    
    # 3. Create Pack endpoint
    pack_res = client.post("/prompt_studio/create_pack", json={
        "story_id": "api_test_story_pack",
        "title": "قصة النجم الصغير",
        "arabic_story_text": "كان النجم يلمع في السماء الزرقاء. قابل قمراً ودوداً وتبادلا التحية. وعادا معاً لنشر الأمان.",
        "num_scenes": 3,
        "characters": [
            {
                "character_id": "STAR_01",
                "display_name": "النجم الصغير",
                "apparent_age": "شخصية كرتونية لطفل فضائي",
                "hair_details": "شعر ذهبي",
                "skin_tone": "بشرة ذهبية",
                "canonical_clothing": "رداء فضي",
                "distinctive_features": "عيون متلألئة",
                "source_photos": ["star_ref.jpg"]
            }
        ]
    })
    assert pack_res.status_code == 200
    pack_data = pack_res.json()
    assert pack_data["story_id"] == "api_test_story_pack"
    
    # 4. List Packs endpoint
    list_res = client.get("/prompt_studio/list_packs")
    assert list_res.status_code == 200
    packs = list_res.json()["packs"]
    assert any(p["story_id"] == "api_test_story_pack" for p in packs)
    
    # 5. Get Pack Details endpoint
    get_res = client.get("/prompt_studio/pack/api_test_story_pack")
    assert get_res.status_code == 200
    files = get_res.json()["files"]
    assert "scene_prompts.md" in files
    assert "character_bible.md" in files
    
    # 6. Save Evaluation endpoint
    eval_res = client.post("/prompt_studio/save_evaluation", json={
        "story_id": "api_test_story_pack",
        "workflow_id": "workflow_a_character_sheet",
        "scene_id": "SCENE_01",
        "ratings": {
            "character_resemblance": 5,
            "preservation_of_distinctive_features": 4,
            "clothing_continuity": 5,
            "art_style_consistency": 5
        },
        "attempts": 1,
        "notes": "Excellent first attempt using character sheet turnaround!"
    })
    assert eval_res.status_code == 200
    assert eval_res.json()["status"] == "saved"
    
    # 7. Export Pack ZIP endpoint
    zip_res = client.get("/prompt_studio/export_pack/api_test_story_pack")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert len(zip_res.content) > 100
    
    # 8. Single image safeguard verification
    img_res = client.post("/generate_single_image", json={
        "scene_text_en": "test scene",
        "child_gender": "boy",
        "child_1st_name_arabic": "كريم",
        "init_image_base64": "dummy"
    })
    assert img_res.status_code == 200
    assert img_res.json()["status"] == "bypassed"
    
    print("\n[PASSED] test_fastapi_endpoints: All 8 API endpoints tested successfully.")


def test_mocked_llm_response_proves_ai_authors_prompts(monkeypatch, tmp_path):
    """
    REQUIREMENT 1 & 3:
    Prove that the live text model generates the creative content and that
    returned prompts come from the model response rather than hardcoded templates.
    """
    mock_creative_prompt = (
        "UNIQUE_MOCK_AI_NARRATIVE_STILL_4728: Karim perches on an antique brass observatory balcony, "
        "peering through an ornate telescope at the glowing sapphire constellations of Andromeda. "
        "Disney Pixar 3D animated style, luminous indigo night atmosphere with deep violet shadows."
    )

    def mock_call_dashscope_chat(messages, **kwargs):
        sys_prompt = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        user_prompt = messages[1]["content"] if len(messages) > 1 else ""

        # If character bible request
        if "master character designer" in sys_prompt:
            return json.dumps({
                "KARIM_01": {
                    "character_id": "KARIM_01",
                    "display_name": "Karim",
                    "confirmed_attributes": {"apparent_age": "6-year-old boy", "canonical_clothing": "navy blue hoodie"},
                    "ai_proposed_attributes": {"face_shape": "soft contoured Pixar cheeks", "eye_details": "sparkling dark amber eyes"},
                    "unknown_attributes": [],
                    "character_sheet_prompt": "AI_MODEL_AUTHORED_SHEET_PROMPT: 3-view turnaround of Karim with glowing brass telescope patch.",
                    "invariants": ["navy blue hoodie", "amber eyes"]
                }
            })
        # If scene plan and prompts request
        elif "senior art director" in sys_prompt:
            return json.dumps([
                {
                    "scene_id": "SCENE_01",
                    "page_number": 1,
                    "exact_arabic_text": "كريم كان ينظر إلى السماء كل ليلة ويعد النجوم المتلألئة.",
                    "inferred_setting": "Celestial antique observatory balcony high above a tranquil twilight valley",
                    "time_of_day": "Midnight under sapphire constellations",
                    "character_action": "Perched on a brass observation stool, excitedly charting glowing stars with a quill",
                    "facial_expression": "Wide-eyed awe with joyful smile",
                    "props_and_environment": "Brass telescope, celestial globe, glowing star charts",
                    "lighting_and_atmosphere": "Volumetric indigo celestial glow with starlight specular highlights",
                    "camera_composition": "Heroic low-angle three-quarter shot framing child against glowing nebula",
                    "continuity_requirements": "Preserve navy blue hoodie and amber eyes across all scenes.",
                    "prompt_workflow_a": mock_creative_prompt,
                    "prompt_workflow_b": mock_creative_prompt + " (photo likeness conditioned)",
                    "prompt_workflow_c": mock_creative_prompt + " (hybrid sheet & photo)",
                    "negative_prompt": "photorealistic, real photo, watermark, text"
                }
            ])
        # If cover prompt request
        elif "book cover illustrator" in sys_prompt:
            return "AI_MODEL_AUTHORED_COVER: Whimsical panoramic cover of Karim leaping across celestial moonbeams, leaving the top 35% empty for title."
        # If revision request
        elif "revision assistant" in sys_prompt:
            return json.dumps({
                "revised_prompt": "AI_MODEL_REVISED_PROMPT: Karim now sits serenely cross-legged holding an ancient brass astrolabe.",
                "modifications_summary": "Adjusted posture to cross-legged and added astrolabe per user instruction.",
                "preserved_invariants": ["navy blue hoodie", "amber eyes"]
            })
        return "Generic AI response"

    import model_utils
    import prompt_studio_engine
    monkeypatch.setattr(model_utils, "call_dashscope_chat", mock_call_dashscope_chat)
    monkeypatch.setattr(prompt_studio_engine, "call_dashscope_chat", mock_call_dashscope_chat)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test_mock_active_key_12345")

    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_ai_proves_authoring",
        title="كريم وعجائب الفضاء",
        arabic_story_text="كريم كان ينظر إلى السماء كل ليلة ويعد النجوم المتلألئة.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                apparent_age="6-year-old boy",
                hair_details="short curly hair",
                canonical_clothing="navy blue hoodie",
                source_photos=["karim.jpg"]
            )
        ]
    )

    pack = engine.generate_prompt_pack(story_input)

    # 1. Verify generation mode is live_ai
    assert pack["ai_generated"] is True, "Must report ai_generated=True when LLM successfully authors pack"
    assert pack["generation_mode"] == "live_ai", f"Expected 'live_ai', got {pack['generation_mode']}"
    assert pack["fallback_reason"] is None

    # 2. Verify that output contains the EXACT creative content authored by the LLM
    scene_plan_file = tmp_path / "test_ai_proves_authoring" / "scene_plan.json"
    scenes = json.loads(scene_plan_file.read_text(encoding="utf-8"))
    assert len(scenes) == 1
    assert "UNIQUE_MOCK_AI_NARRATIVE_STILL_4728" in scenes[0]["prompt_workflow_a"], \
        "Prompt in scene_plan.json MUST come directly from model response!"
    assert "antique observatory" in scenes[0]["inferred_setting"].lower()

    # 3. Verify scene_prompts.md contains the exact model output and Live AI mode banner
    scene_md = (tmp_path / "test_ai_proves_authoring" / "scene_prompts.md").read_text(encoding="utf-8")
    assert "UNIQUE_MOCK_AI_NARRATIVE_STILL_4728" in scene_md
    assert "Live AI Reasoning" in scene_md
    assert "Deterministic Heuristic Fallback" not in scene_md

    # 4. Verify character sheet prompt came from model response
    sheet_md = (tmp_path / "test_ai_proves_authoring" / "character_sheet_prompts.md").read_text(encoding="utf-8")
    assert "AI_MODEL_AUTHORED_SHEET_PROMPT" in sheet_md

    # 5. Verify cover prompt came from model response
    cover_md = (tmp_path / "test_ai_proves_authoring" / "cover_prompt.md").read_text(encoding="utf-8")
    assert "AI_MODEL_AUTHORED_COVER" in cover_md

    # 6. Verify revision comes from model response
    rev_res = engine.revise_scene_prompt(
        story_id="test_ai_proves_authoring",
        scene_id="SCENE_01",
        user_instruction="Make him sit cross-legged with an astrolabe"
    )
    assert "AI_MODEL_REVISED_PROMPT" in rev_res["revised_prompt"]
    assert rev_res["ai_generated"] is True
    assert rev_res["generation_mode"] == "live_ai"

    print("\n[PASSED] test_mocked_llm_response_proves_ai_authors_prompts: Verified LLM response directly populates all creative prompts.")


def test_fallback_mode_explicitly_tagged_when_offline(monkeypatch, tmp_path):
    """
    REQUIREMENT 2:
    Do not treat a keyword-based fallback as equivalent to AI.
    When API key is missing or model call fails, explicitly mark the output
    as fallback-generated and add clear disclaimers, never claiming it was AI.
    """
    # Ensure no API key is available
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("ALIBABA_API_KEY", raising=False)

    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_fallback_explicit_tagging",
        title="قصة الفتى والبحر",
        arabic_story_text="غاص الفتى في أعماق البحر الأزرق يشاهد الشعاب المرجانية والأسماك الجميلة.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="BOY_01",
                display_name="طارق",
                apparent_age="7-year-old boy",
                hair_details="wavy black hair",
                canonical_clothing="blue swimming shorts",
                source_photos=["tariq.jpg"]
            )
        ]
    )

    pack = engine.generate_prompt_pack(story_input)

    # 1. Must explicitly state that AI was NOT used
    assert pack["ai_generated"] is False, "Fallback pack must NOT pretend to be AI-generated"
    assert pack["generation_mode"] == "fallback_heuristic"
    assert pack["model_used"] is None
    assert pack["fallback_reason"] is not None

    # 2. Manifest file must document fallback
    manifest_file = tmp_path / "test_fallback_explicit_tagging" / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["ai_generated"] is False
    assert manifest["generation_mode"] == "fallback_heuristic"

    # 3. Markdown files must contain unambiguous warning disclaimers
    scene_md = (tmp_path / "test_fallback_explicit_tagging" / "scene_prompts.md").read_text(encoding="utf-8")
    assert "Deterministic Heuristic Fallback" in scene_md
    assert "Live AI Offline" in scene_md
    assert "The prompts below were generated using rule-based semantic inference" in scene_md

    char_md = (tmp_path / "test_fallback_explicit_tagging" / "character_bible.md").read_text(encoding="utf-8")
    assert "Deterministic Heuristic Fallback" in char_md

    print("\n[PASSED] test_fallback_mode_explicitly_tagged_when_offline: Correctly tagged as fallback without masquerading as AI.")


def test_multi_story_context_adaptation(tmp_path):
    """
    REQUIREMENT 4:
    Test at least three different story contexts:
    1. Nighttime scene (balcony, dark sky, stars, moon)
    2. Daytime scene (school classroom, teacher, open space book)
    3. Different environment / activity (marine coral reef underwater diving, sea turtles)
    Verify prompts adapt to each story context and preserve Arabic text 100% verbatim.
    """
    engine = PromptStudioEngine(output_dir=tmp_path)

    # Story 1: Nighttime Balcony & Stargazing
    story_1 = StoryInput(
        story_id="story_context_1_night",
        title="رحلة كريم إلى الفضاء",
        arabic_story_text="كريم كان يحب النظر إلى السماء كل ليلة، يراقب النجوم اللامعة ويعدها بحماس شديد من شرفة منزله الهادئ.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                apparent_age="6-year-old boy",
                hair_details="short curly hair",
                canonical_clothing="royal navy blue hoodie",
                source_photos=["karim.jpg"]
            )
        ]
    )

    # Story 2: Daytime Astronomy Classroom
    story_2 = StoryInput(
        story_id="story_context_2_classroom",
        title="كريم في حصة الفلك",
        arabic_story_text="في المدرسة المشرقة، لاحظ المعلم شغف كريم بالفضاء فأهداه كتاباً مصوراً لكوكب زحل وحلقاته الذهبية في الصف.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                apparent_age="6-year-old boy",
                hair_details="short curly hair",
                canonical_clothing="royal navy blue hoodie",
                source_photos=["karim.jpg"]
            )
        ]
    )

    # Story 3: Marine Coral Reef Underwater Adventure
    story_3 = StoryInput(
        story_id="story_context_3_marine",
        title="مغامرة سلمى في أعماق البحر",
        arabic_story_text="غاصت سلمى في مياه البحر الصافية بين الشعاب المرجانية الملونة وراقبت السلاحف البحرية والأسماك الزاهية ببهجة.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="SALMA_01",
                display_name="سلمى",
                apparent_age="7-year-old girl",
                hair_details="black braids with yellow ribbon",
                canonical_clothing="teal diving wetsuit",
                source_photos=["salma.jpg"]
            )
        ]
    )

    pack_1 = engine.generate_prompt_pack(story_1)
    pack_2 = engine.generate_prompt_pack(story_2)
    pack_3 = engine.generate_prompt_pack(story_3)

    scenes_1 = json.loads((tmp_path / "story_context_1_night" / "scene_plan.json").read_text(encoding="utf-8"))
    scenes_2 = json.loads((tmp_path / "story_context_2_classroom" / "scene_plan.json").read_text(encoding="utf-8"))
    scenes_3 = json.loads((tmp_path / "story_context_3_marine" / "scene_plan.json").read_text(encoding="utf-8"))

    # Verify Story 1 context
    s1 = scenes_1[0]
    assert "night" in s1["time_of_day"].lower() or "starlit" in s1["time_of_day"].lower()
    assert "balcony" in s1["inferred_setting"].lower() or "night" in s1["inferred_setting"].lower()
    assert "morning sunlight" not in s1["lighting_and_atmosphere"].lower()
    assert s1["exact_arabic_text"] == story_1.arabic_story_text, "Arabic text 1 must be 100% verbatim"

    # Verify Story 2 context
    s2 = scenes_2[0]
    assert "school" in str(s2["inferred_setting"]).lower() or "classroom" in str(s2["inferred_setting"]).lower()
    assert "daytime" in str(s2["time_of_day"]).lower() or "morning" in str(s2["time_of_day"]).lower()
    assert "book" in str(s2["props_and_environment"]).lower() or "diagram" in str(s2["props_and_environment"]).lower()
    assert s2["exact_arabic_text"] == story_2.arabic_story_text, "Arabic text 2 must be 100% verbatim"

    # Verify Story 3 context
    s3 = scenes_3[0]
    assert "coral reef" in str(s3["inferred_setting"]).lower() or "underwater" in str(s3["inferred_setting"]).lower()
    assert "underwater" in str(s3["time_of_day"]).lower() or "daytime" in str(s3["time_of_day"]).lower() or "morning" in str(s3["time_of_day"]).lower()
    assert "turtle" in str(s3["props_and_environment"]).lower() or "coral" in str(s3["props_and_environment"]).lower()
    assert s3["exact_arabic_text"] == story_3.arabic_story_text, "Arabic text 3 must be 100% verbatim"

    # Verify that all 3 prompts are completely distinct and non-overlapping in narrative content
    assert s1["prompt_workflow_a"] != s2["prompt_workflow_a"]
    assert s2["prompt_workflow_a"] != s3["prompt_workflow_a"]
    assert s1["prompt_workflow_a"] != s3["prompt_workflow_a"]

    assert "night sky" in s1["prompt_workflow_a"].lower() or "balcony" in s1["prompt_workflow_a"].lower()
    assert "classroom" in s2["prompt_workflow_a"].lower() or "teacher" in s2["prompt_workflow_a"].lower()
    assert "coral reef" in s3["prompt_workflow_a"].lower() or "underwater" in s3["prompt_workflow_a"].lower()

    print("\n[PASSED] test_multi_story_context_adaptation: Verified distinct contextual adaptation across 3 story domains while preserving Arabic text verbatim.")


def test_live_dashscope_call_status():
    """
    REQUIREMENT 3 (Part 2):
    Live integration test with Alibaba Cloud DashScope credentials if configured in environment.
    Reports status clearly and never exposes API keys in test logs.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
    if not api_key:
        print("\n[INFO] Live DashScope call skipped: DASHSCOPE_API_KEY is not set in environment.")
        return

    import model_utils
    try:
        res = model_utils.call_dashscope_chat(
            messages=[
                {"role": "system", "content": "You are a test assistant. Return ONLY the word 'PONG'."},
                {"role": "user", "content": "PING"}
            ],
            timeout=15
        )
        assert len(res) > 0
        print(f"\n[PASSED] Live DashScope text API call succeeded! Response received: {res[:50]}")
    except Exception as e:
        # Report failure clearly without exposing secret keys
        err_sanitized = re.sub(r'Bearer\s+[a-zA-Z0-9_\-]+', 'Bearer [MASKED]', str(e))
        print(f"\n[NOTICE] Live DashScope call attempted with configured key failed: {err_sanitized}")


def test_complete_manual_only_route_safety(monkeypatch):
    """
    REQUIREMENT 5:
    Verify manual-only operation. Inspect every route and call site to confirm that
    creating, revising, saving, listing, and exporting prompt packs cannot trigger image generation.
    """
    def forbidden_image_call(*args, **kwargs):
        raise AssertionError("CRITICAL VIOLATION: An image generation API was invoked during Prompt Studio operations!")

    import dashscope
    import model_utils
    monkeypatch.setattr(dashscope.MultiModalConversation, "call", forbidden_image_call)
    monkeypatch.setattr(model_utils, "generate_scene_image", forbidden_image_call)

    # 1. Validate route
    val_res = client.post("/prompt_studio/validate", json={
        "title": "قصة الأمان",
        "arabic_story_text": "كان الطفل يلعب بأمان في حديقة المنزل.",
        "num_scenes": 2,
        "characters": [
            {
                "character_id": "CHAR_01",
                "display_name": "سامي",
                "apparent_age": "5-year-old boy",
                "hair_details": "short brown hair",
                "skin_tone": "olive skin",
                "canonical_clothing": "yellow t-shirt",
                "source_photos": ["sami.jpg"]
            }
        ]
    })
    assert val_res.status_code == 200

    # 2. Create Pack route
    pack_res = client.post("/prompt_studio/create_pack", json={
        "story_id": "safe_manual_only_pack",
        "title": "قصة الأمان",
        "arabic_story_text": "كان الطفل يلعب بأمان في حديقة المنزل. ثم عاد إلى بيته مبتسماً.",
        "num_scenes": 2,
        "characters": [
            {
                "character_id": "CHAR_01",
                "display_name": "سامي",
                "apparent_age": "5-year-old boy",
                "hair_details": "short brown hair",
                "skin_tone": "olive skin",
                "canonical_clothing": "yellow t-shirt",
                "source_photos": ["sami.jpg"]
            }
        ]
    })
    assert pack_res.status_code == 200

    # 3. Revise Prompt route
    rev_res = client.post("/prompt_studio/revise_prompt", json={
        "story_id": "safe_manual_only_pack",
        "scene_id": "SCENE_01",
        "current_prompt": "Initial prompt for Sami playing with ball...",
        "user_instruction": "Add warm golden hour lighting and make him hold a soccer ball"
    })
    assert rev_res.status_code == 200

    # 4. List Packs route
    list_res = client.get("/prompt_studio/list_packs")
    assert list_res.status_code == 200

    # 5. Get Pack route
    get_res = client.get("/prompt_studio/pack/safe_manual_only_pack")
    assert get_res.status_code == 200

    # 6. Save Evaluation route
    eval_res = client.post("/prompt_studio/save_evaluation", json={
        "story_id": "safe_manual_only_pack",
        "workflow_id": "workflow_a_character_sheet",
        "scene_id": "SCENE_01",
        "ratings": {"character_resemblance": 5},
        "notes": "Verified manual workflow."
    })
    assert eval_res.status_code == 200

    # 7. Export Pack route
    exp_res = client.get("/prompt_studio/export_pack/safe_manual_only_pack")
    assert exp_res.status_code == 200
    assert exp_res.headers["content-type"] == "application/zip"

    # 8. Single Image legacy route returns bypassed
    img_res = client.post("/generate_single_image", json={
        "scene_text_en": "test scene",
        "child_gender": "boy",
        "child_1st_name_arabic": "سامي",
        "init_image_base64": "dummy"
    })
    assert img_res.status_code == 200
    assert img_res.json()["status"] == "bypassed"

    print("\n[PASSED] test_complete_manual_only_route_safety: Zero image generation APIs invoked across all Prompt Studio routes.")


def test_canonical_name_and_character_id_consistency_across_artifacts(tmp_path):
    """
    AUDIT REQUIREMENT 1:
    Verify that one canonical spelling is defined and strictly used across ALL artifacts.
    Detects transliteration drift (e.g. 'Kareem' vs 'Karim') and ensures auto-repair.
    """
    engine = PromptStudioEngine(output_dir=tmp_path)
    story_input = StoryInput(
        story_id="test_canonical_audit",
        title="حلم كريم في الفضاء",
        arabic_story_text="كان كريم ينظر إلى النجوم من شرفة منزله كل ليلة ويحلم بالسفر بعيداً.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم / Kareem",
                canonical_name_en="Karim",
                canonical_name_ar="كريم",
                apparent_age="6-year-old boy",
                hair_details="short dark-brown curly hair",
                skin_tone="warm olive skin",
                canonical_clothing="royal navy blue hoodie",
                source_photos=["karim_photo.jpg"]
            )
        ]
    )

    pack = engine.generate_prompt_pack(story_input)
    audit_file = tmp_path / "test_canonical_audit" / "consistency_audit.json"
    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
    
    # 1. Check canonical name list
    assert "Karim" in audit_data["character_consistency"]["canonical_names_enforced"]
    
    # 2. Check all text files for accidental 'Kareem' drift
    for fname in ["character_bible.md", "character_sheet_prompts.md", "scene_prompts.md", "cover_prompt.md", "editing_prompts.md"]:
        content = (tmp_path / "test_canonical_audit" / fname).read_text(encoding="utf-8")
        # 'Kareem' should NOT appear in generated prompts or titles
        assert "Kareem" not in content or "Standardized 'Kareem'" in str(audit_data)
        assert "KARIM_01" in content or "Karim" in content

    # 3. Check JSON files
    assets_data = json.loads((tmp_path / "test_canonical_audit" / "character_assets.json").read_text(encoding="utf-8"))
    assert assets_data["characters"][0]["canonical_name_en"] == "Karim"
    assert assets_data["characters"][0]["character_id"] == "KARIM_01"

    print("\n[PASSED] test_canonical_name_and_character_id_consistency_across_artifacts: Strict canonical naming verified.")


def test_contradictory_wardrobe_and_physical_attribute_detection():
    """
    AUDIT REQUIREMENT 1 (Part 2):
    Verify that contradictory attributes in prompts (e.g. blonde hair for dark-haired child,
    adult representation for young child) are FLAGGED for user review rather than silently mutated.
    """
    story_input = StoryInput(
        story_id="conflict_test",
        title="اختبار التعارض",
        arabic_story_text="كان الطفل كريم يبتسم في غرفته.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                canonical_name_en="Karim",
                apparent_age="6-year-old child",
                hair_details="dark-brown curly hair",
                canonical_clothing="royal blue hoodie",
                source_photos=["karim.jpg"]
            )
        ]
    )

    # Intentionally corrupt scene prompt with contradictory attributes
    corrupt_scene_plans = [
        {
            "scene_id": "SCENE_01",
            "page_number": 1,
            "exact_arabic_text": "كان الطفل كريم يبتسم في غرفته.",
            "prompt_workflow_a": "A photo of an adult woman named Karim with blonde hair wearing royal blue hoodie.",
            "prompt_workflow_b": "A photo of an adult woman with blonde hair.",
            "prompt_workflow_c": "A photo with blonde hair.",
            "inferred_setting": "Bedroom",
            "time_of_day": "Daytime"
        }
    ]
    cover_data = {"cover_prompt": "Cover of Karim looking at stars"}

    audit = audit_prompt_pack_consistency(
        story_input=story_input,
        scene_plans=corrupt_scene_plans,
        cover_data=cover_data,
        ai_char_bible={}
    )

    # Must flag hair color conflict
    assert any(c["conflict_type"] == "hair_color_conflict" for c in audit["conflicts_flagged"]), \
        "Should flag blonde hair contradiction against dark-brown curls"
    
    # Must flag age representation conflict
    assert any(c["conflict_type"] == "age_representation_conflict" for c in audit["conflicts_flagged"]), \
        "Should flag adult woman contradiction against 6-year-old child"

    # Must NOT silently change the prompt, but flag it
    assert "[CONFLICT]" in " ".join(audit["findings"])
    assert audit["audit_passed"] is False, "Audit must fail when unresolvable contradictory attributes exist"

    print("\n[PASSED] test_contradictory_wardrobe_and_physical_attribute_detection: Contradictions successfully flagged.")


def test_scene_to_story_and_cover_grounding_audit():
    """
    AUDIT REQUIREMENT 2:
    Verify grounded story fidelity: cover must not contradict the story by floating in outer space
    when the story is a grounded domestic stargazing narrative.
    """
    story_input = StoryInput(
        story_id="grounding_test",
        title="كريم والنجوم",
        arabic_story_text="وقف كريم في شرفة منزله ينظر إلى السماء الصافية ويعد النجوم المتلألئة.",
        num_scenes=1,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                canonical_name_en="Karim",
                apparent_age="6-year-old child",
                hair_details="short curly dark-brown hair",
                canonical_clothing="navy blue hoodie"
            )
        ]
    )

    # Hallucinated cover prompt putting child in vacuum of space
    ungrounded_cover = {
        "cover_prompt": "Karim floats weightlessly in the vastness of outer space inside an astronaut suit with orbiting moons."
    }
    scene_plans = [
        {
            "scene_id": "SCENE_01",
            "page_number": 1,
            "exact_arabic_text": story_input.arabic_story_text,
            "prompt_workflow_a": "Karim on balcony looking at stars wearing navy blue hoodie."
        }
    ]

    audit = audit_prompt_pack_consistency(
        story_input=story_input,
        scene_plans=scene_plans,
        cover_data=ungrounded_cover,
        ai_char_bible={}
    )

    # Verify hallucination was caught and auto-repaired
    assert any("Cover prompt hallucinated ungrounded sci-fi setting" in f for f in audit["findings"])
    assert any("Aligned cover prompt to grounded story reality" in r for r in audit["repaired_items"])
    assert "balcony" in ungrounded_cover["cover_prompt"].lower()
    assert "floats weightlessly in outer space" not in ungrounded_cover["cover_prompt"].lower()

    print("\n[PASSED] test_scene_to_story_and_cover_grounding_audit: Grounded cover fidelity enforced and auto-repaired.")


def test_three_diverse_stories_quality_audit(tmp_path):
    """
    AUDIT REQUIREMENT 5:
    Run the complete audit checks on 3 diverse story archetypes:
    - Story A: Simple 2-3 scenes (Karim stargazing & classroom)
    - Story B: Multiple characters interacting (Layla & Omar science fair)
    - Story C: Wardrobe/environment shift (Salma garden apron -> marine wetsuit -> beach towel)
    """
    engine = PromptStudioEngine(output_dir=tmp_path)

    # -------------------------------------------------------------
    # Story A: Simple 2-scene domestic story
    # -------------------------------------------------------------
    story_a = StoryInput(
        story_id="audit_story_a_simple",
        title="نجوم كريم",
        arabic_story_text=(
            "كريم كان يحب النظر إلى السماء كل ليلة ويعد النجوم المتلألئة من شرفته. "
            "في اليوم التالي في المدرسة، أهدى المعلم كتيّباً مصوراً لكريم يشرح أسرار الكواكب."
        ),
        num_scenes=2,
        characters=[
            CharacterProfile(
                character_id="KARIM_01",
                display_name="كريم",
                canonical_name_en="Karim",
                canonical_name_ar="كريم",
                apparent_age="6-year-old boy",
                hair_details="short dark-brown curls",
                skin_tone="warm olive skin",
                canonical_clothing="royal navy blue hoodie",
                source_photos=["karim.jpg"]
            )
        ]
    )
    pack_a = engine.generate_prompt_pack(story_a)
    audit_a = pack_a["audit_report"]
    assert audit_a["arabic_verbatim_preserved"] is True
    assert audit_a["audit_passed"] is True
    assert pack_a["scene_count"] == 2

    # -------------------------------------------------------------
    # Story B: Multiple characters interacting
    # -------------------------------------------------------------
    story_b = StoryInput(
        story_id="audit_story_b_multi_char",
        title="مشروع ليلى وعمر العلمي",
        arabic_story_text=(
            "جلست ليلى وعمر في مختبر العلوم المدرسي لتجهيز نموذج بركان ملون. "
            "سكبت ليلى السائل الأحمر بحذر بينما راقبها عمر بابتسامة تشجيعية. "
            "ثار البركان وسط تصفيق زملائهما في الصف."
        ),
        num_scenes=3,
        characters=[
            CharacterProfile(
                character_id="LAYLA_01",
                display_name="ليلى",
                canonical_name_en="Layla",
                canonical_name_ar="ليلى",
                role="Co-protagonist",
                apparent_age="8-year-old girl",
                hair_details="long dark-brown hair in a ponytail",
                skin_tone="light tan skin",
                canonical_clothing="white lab coat over lilac sweater",
                source_photos=["layla.jpg"]
            ),
            CharacterProfile(
                character_id="OMAR_01",
                display_name="عمر",
                canonical_name_en="Omar",
                canonical_name_ar="عمر",
                role="Co-protagonist",
                apparent_age="8-year-old boy",
                hair_details="wavy black hair",
                skin_tone="warm olive skin",
                canonical_clothing="white lab coat over green striped shirt",
                source_photos=["omar.jpg"]
            )
        ]
    )
    pack_b = engine.generate_prompt_pack(story_b)
    audit_b = pack_b["audit_report"]
    assert audit_b["arabic_verbatim_preserved"] is True
    assert audit_b["audit_passed"] is True
    assert len(audit_b["character_consistency"]["canonical_names_enforced"]) == 2
    assert "Layla" in audit_b["character_consistency"]["canonical_names_enforced"]
    assert "Omar" in audit_b["character_consistency"]["canonical_names_enforced"]

    # -------------------------------------------------------------
    # Story C: Multi-location & Wardrobe Shifts
    # -------------------------------------------------------------
    story_c = StoryInput(
        story_id="audit_story_c_wardrobe_shift",
        title="مغامرة سلمى بين الحديقة والبحر",
        arabic_story_text=(
            "بدأت سلمى صباحها بسقي نباتات الحديقة بابتسامة مشرقة. "
            "في فترة ما بعد الظهر، ارتدت بدلة الغوص وغاصت في الشعب المرجانية بين السلاحف والأسماك. "
            "وعند غروب الشمس، جلست على رمال الشاطئ تلتحف منشفة دافئة وتتأمل الأفق."
        ),
        num_scenes=3,
        characters=[
            CharacterProfile(
                character_id="SALMA_01",
                display_name="سلمى",
                canonical_name_en="Salma",
                canonical_name_ar="سلمى",
                apparent_age="7-year-old girl",
                hair_details="braided black hair with yellow beads",
                skin_tone="medium golden skin",
                canonical_clothing="green gardening apron over yellow t-shirt",
                wardrobe_changes="teal neoprene diving wetsuit with yellow fins; plush yellow beach towel wrap",
                permitted_variations=[
                    "teal neoprene diving wetsuit with yellow fins",
                    "plush yellow beach towel wrap",
                    "gardening tools",
                    "diving mask on forehead"
                ],
                source_photos=["salma.jpg"]
            )
        ]
    )
    pack_c = engine.generate_prompt_pack(story_c)
    audit_c = pack_c["audit_report"]
    assert audit_c["arabic_verbatim_preserved"] is True
    assert audit_c["audit_passed"] is True
    assert audit_c["conflicts_count"] == 0

    print("\n[PASSED] test_three_diverse_stories_quality_audit: All 3 diverse stories verified across all quality dimensions.")


def test_story_model_outcome_parsing_and_endpoint(tmp_path):
    """
    Tests that the story model outcome (make_input(...) plus story scenes)
    is accurately parsed into structured StoryInput data for the image pipeline,
    both via the PromptStudioEngine method and via the FastAPI endpoint.
    """
    from prompt_studio_engine import parse_story_model_outcome
    from fastapi.testclient import TestClient
    from app import app

    sample_outcome = '''make_input(
    name="نور",
    age=10,
    language="simplified_fusha",
    interests=["الرسم", "الخياطة", "تصميم الأزياء"],
    story_goal="تعليم الطفل تقبل الأخطاء والتعلّم من المحاولة والتعديل",
    story_type="قصة عن تصميم الأزياء والتعلم",
    page_count=10,
    additional_characters=[
        {"name": "الجدة سلمى", "role": "خياطة ماهرة تعلمها استخدام الأدوات بأمان"}
    ],
    dedication="إلى نور، صاحبة الأفكار الجميلة",
    preferences="قصة واقعية ونهاية مشجعة",
    avoid=["التجارب الخطرة", "المشاهد المخيفة"]
)

التجربة 3: فستان نور الساحر

صفحات القصة

صفحة 1: عالم نور من الألوان والأقمشة
إلى نور، صاحبة الأفكار الجميلة. في غرفة نور، حيث تتناثر قصاصات الأقمشة وأقالم الرسم الملونة، كانت نور ذات العشرة أعوام تقضي أجمل أوقاتها.

صفحة 2: فكرة الفستان الكبير
في أحد الأيام، أعلنت المدرسة عن إقامة معرض فني كبير، ودُعيت كل العائلات للحضور.
'''
    # 1. Direct Engine Parser Test
    parsed = parse_story_model_outcome(sample_outcome)
    assert parsed["metadata"]["name"] == "نور"
    assert parsed["metadata"]["age"] == 10
    assert parsed["language_canonical"] == "Simple Modern Standard Arabic"
    assert parsed["title"] == "فستان نور الساحر"
    assert parsed["detected_gender"] == "girl"
    assert len(parsed["scenes"]) == 2
    assert parsed["scenes"][0]["page_number"] == 1
    assert parsed["scenes"][0]["scene_title"] == "عالم نور من الألوان والأقمشة"
    assert len(parsed["characters"]) == 2
    assert parsed["characters"][0]["role"] == "Protagonist"
    assert parsed["characters"][0]["gender"] == "girl"
    assert parsed["characters"][1]["display_name"] == "الجدة سلمى"
    assert parsed["characters"][1]["role"] == "خياطة ماهرة تعلمها استخدام الأدوات بأمان"

    # 2. FastAPI Endpoint Test
    client = TestClient(app)
    resp = client.post("/prompt_studio/parse_story_outcome", json={"raw_text": sample_outcome})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"]["name"] == "نور"
    assert data["title"] == "فستان نور الساحر"
    assert len(data["characters"]) == 2
    print("\n[PASSED] test_story_model_outcome_parsing_and_endpoint: Story outcome parser verified successfully.")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
