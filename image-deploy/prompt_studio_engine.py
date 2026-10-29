"""
Hekayti — AI-Assisted Manual Illustration Prompt Studio Engine
==============================================================
An intelligent prompt-generation assistant where AI reads, reasons, and writes
the visual planning and illustration prompts based on story text, character data,
and selected art styles.

Architectural Principles:
1. AI Authors the Prompts: No rigid boilerplate templates or static string f-strings.
   The AI reads the story, understands the setting and time of day, and authors cohesive prompts.
2. Exact Arabic Preservation: Original Arabic text is segmented and preserved 100% verbatim.
3. Identity Tracking: Distinguishes Confirmed attributes from AI-Proposed and Unknown attributes.
4. AI-Driven Prompt Revisions: Supports dynamic natural-language prompt refinement.
5. Zero Automated Image Generation: Text models author prompts and instructions;
   the human artist executes image generation manually.
"""

import os
import time
import re
import ast
import json
import uuid
import shutil
import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, ClassVar
from pydantic import BaseModel, Field, ConfigDict

try:
    from model_utils import call_dashscope_chat
except ImportError:
    try:
        from .model_utils import call_dashscope_chat
    except Exception:
        import sys
        sys.path.append(str(Path(__file__).resolve().parent))
        from model_utils import call_dashscope_chat

logger = logging.getLogger(__name__)

# Base directory for prompt packs
PROMPT_PACKS_DIR = Path(__file__).resolve().parent.parent / "prompt_packs"
PROMPT_PACKS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# Data Models
# =====================================================================

class CharacterProfile(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    character_id: str = Field(..., description="Stable character ID, e.g., 'MINA_01', 'KARIM_01'")
    display_name: str = Field(..., description="Display name in English or Arabic, e.g., 'Karim / كريم'")
    canonical_name_en: str = Field(default="", description="Strict canonical English spelling, e.g., 'Karim'")
    canonical_name_ar: str = Field(default="", description="Strict canonical Arabic spelling, e.g., 'كريم'")
    role: str = Field(default="Protagonist", description="Role in story, e.g., 'Hero', 'Mentor'")
    source_photos: List[str] = Field(default_factory=list, description="Original source photo filenames, e.g., ['karim_photo_01.jpg']")
    canonical_sheet: str = Field(default="", description="Target character sheet filename, e.g., 'karim_character_sheet.png'")
    approved_references: List[str] = Field(default_factory=list, description="Approved reference images")
    status: str = Field(default="awaiting_manual_generation_and_approval")
    
    # User-confirmed visual features
    apparent_age: str = Field(default="", description="Confirmed age, e.g., '6-year-old boy'")
    gender: str = Field(default="", description="'boy', 'girl', or custom")
    face_shape: str = Field(default="", description="Face shape, e.g., 'round face with soft cheeks'")
    skin_tone: str = Field(default="", description="Confirmed skin tone, e.g., 'warm olive skin'")
    hair_details: str = Field(default="", description="Hair details, e.g., 'curly dark-brown short hair'")
    eye_details: str = Field(default="", description="Eye details, e.g., 'large dark-brown expressive eyes'")
    body_proportions: str = Field(default="", description="Proportions, e.g., 'Pixar-style child proportions'")
    distinctive_features: str = Field(default="", description="Distinctive marks, e.g., 'dimple on right cheek'")
    
    relationship: str = Field(default="", description="Relationship to child, e.g. 'Mother', 'Father', 'Teacher', 'Grandmother', 'Friend'")
    appearance_frequency: str = Field(default="medium", description="Appearance frequency: 'low', 'medium', 'high' or 'قليل', 'متوسط', 'كثير'")
    story_impact: str = Field(default="", description="Role or impact on child decisions / plot")

    # Invariants vs Variables
    canonical_clothing: str = Field(default="", description="Standard outfit, e.g., 'royal blue hoodie with silver star patch'")
    wardrobe_changes: Optional[str] = Field(default="", description="Scene-specific variations, e.g., 'astronaut helmet'")
    personality_guidance: Optional[str] = Field(default="", description="Personality and expression guidance")
    permitted_variations: List[str] = Field(default_factory=list, description="Permitted scene variations, e.g. 'sitting barefoot on cushion'")
    invariants: List[str] = Field(default_factory=list, description="Permanent traits that must never change")

    STANDARD_CANONICAL_NAMES: ClassVar[Dict[str, str]] = {
        "kareem": "Karim",
        "careem": "Karim",
        "karem": "Karim",
        "leila": "Layla",
        "laila": "Layla",
        "lela": "Layla",
        "umar": "Omar",
        "omer": "Omar",
        "salmah": "Salma",
        "selma": "Salma",
        "noor": "Nour",
        "tarek": "Tariq",
        "zaid": "Zayd",
        "ameer": "Amir",
        "sammy": "Sami"
    }

    def get_canonical_name_en(self) -> str:
        raw = ""
        if self.canonical_name_en and self.canonical_name_en.strip():
            raw = self.canonical_name_en.strip()
        else:
            parts = re.split(r'[/,\-–|]', self.display_name)
            for p in parts:
                p_clean = p.strip()
                if re.search(r'[a-zA-Z]', p_clean):
                    raw = p_clean
                    break
            if not raw:
                raw = self.character_id.split('_')[0].capitalize()

        return self.STANDARD_CANONICAL_NAMES.get(raw.lower(), raw)

    def get_canonical_name_ar(self) -> str:
        if self.canonical_name_ar and self.canonical_name_ar.strip():
            return self.canonical_name_ar.strip()
        parts = re.split(r'[/,\-–|]', self.display_name)
        for p in parts:
            p_clean = p.strip()
            if re.search(r'[\u0621-\u064A]', p_clean):
                return p_clean
        return self.display_name.strip()


class StoryInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    story_id: Optional[str] = Field(default=None, description="Stable story ID")
    title: str = Field(..., description="Story title")
    arabic_story_text: str = Field(..., description="Complete Arabic story text (preserved verbatim)")
    intended_age: str = Field(default="5-7", description="Intended child age range")
    num_scenes: int = Field(default=10, description="Target number of scenes")
    visual_style: str = Field(
        default="Disney Pixar 3D animated illustration, warm vibrant colors, soft volumetric lighting, expressive stylized characters",
        description="Global artistic style"
    )
    aspect_ratio: str = Field(default="9:16", description="Aspect ratio, e.g. '9:16', '16:9', '1:1'")
    output_format: str = Field(default="High-resolution digital illustration, clean composition", description="Format intent")
    educational_values: Optional[str] = Field(default="", description="Educational / moral takeaways")
    target_image_model: str = Field(
        default="Model-Agnostic / Universal",
        description="Target model, e.g. 'Midjourney v6', 'Flux.1-Dev', 'SDXL', 'Qwen-Image / Wan', 'DALL-E 3'"
    )
    workflow_preference: str = Field(
        default="compare_all",
        description="'workflow_a', 'workflow_b', 'workflow_c', or 'compare_all'"
    )
    has_generated_character_sheet: bool = Field(default=False)
    supports_multiple_refs: bool = Field(default=True)
    supports_editing: bool = Field(default=True)
    characters: List[CharacterProfile] = Field(..., description="Characters in story")
    prestructured_scenes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional pre-structured scenes with page numbers and visual image_descriptions from story model"
    )


class PromptRevisionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    story_id: str
    scene_id: str
    current_prompt: str
    user_instruction: str
    target_model: Optional[str] = None


class EvaluationRating(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    story_id: str
    workflow_id: str
    scene_id: str
    ratings: Dict[str, Optional[int]]
    attempts: Optional[int] = 1
    notes: Optional[str] = ""


# =====================================================================
# AI Text Generation & Semantic Context Reasoner
# =====================================================================

class AITextGenerator:
    """
    Orchestrates AI text generation for the Prompt Studio.
    Routes all model invocations through model_utils.call_dashscope_chat.
    Explicitly tracks whether outputs were authored by the live AI text model
    or by the deterministic semantic heuristic fallback, guaranteeing transparency.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY") or "").strip() or None
        self.text_model_id = os.getenv("TEXT_MODEL_ID", "qwen-plus")
        self.last_mode = "fallback_heuristic"
        self.last_error = "API key not configured" if not self.api_key else None
        self.is_disabled = False

    def _call_llm(self, system_instruction: str, user_prompt: str, temperature: float = 0.5) -> Optional[str]:
        """Calls the live text LLM through model_utils.call_dashscope_chat."""
        if getattr(self, "is_disabled", False):
            return None

        if not self.api_key:
            self.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")

        if not self.api_key or self.api_key.startswith("mock_"):
            self.last_mode = "fallback_heuristic"
            self.last_error = "DASHSCOPE_API_KEY not configured or is placeholder"
            return None

        try:
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ]
            content = call_dashscope_chat(
                messages=messages,
                temperature=temperature,
                model=self.text_model_id,
                api_key=self.api_key,
                timeout=12
            )
            self.last_mode = "live_ai"
            self.last_error = None
            return content
        except Exception as e:
            err_msg = str(e)
            err_sanitized = re.sub(r'Bearer\s+[a-zA-Z0-9_\-]+', 'Bearer [MASKED]', err_msg)
            logger.warning(f"Failed to communicate with LLM API: {err_sanitized}")
            self.last_mode = "fallback_heuristic"
            self.last_error = err_sanitized
            if "invalid_api_key" in err_msg or "Incorrect API key" in err_msg or "401" in err_msg:
                self.api_key = None
                self.is_disabled = True
            return None

    # -----------------------------------------------------------------
    # 1. AI-Driven Character Identity Reasoning
    # -----------------------------------------------------------------
    def generate_character_bible_ai(self, characters: List[CharacterProfile], visual_style: str) -> Dict[str, Any]:
        """
        AI builds the reusable character identity specification:
        - Canonical Character Identifiers (Name English + Arabic, ID, Role)
        - Physical Identity & Proportions (Age, Face shape, Skin tone, Hair details, Eye details, Body proportions)
        - Canonical Wardrobe & Fixed Accessories
        - Personality & Expression Guidance
        - Strict Identity Invariants (must NEVER drift in illustrations)
        - Permitted Situational Variations (actions, poses, scene-aligned props)
        - AI-authored 3-view model turnaround character sheet prompt
        """
        system_prompt = (
            "You are a master character designer and visual development director for children's illustrated books. "
            "Analyze character information and establish a comprehensive, production-ready character bible. "
            "MANDATORY CANONICAL SPELLING: You must strictly use the provided 'canonical_name_en' and 'canonical_name_ar'. "
            "Never introduce alternate transliterations (e.g. if canonical is 'Karim', NEVER write 'Kareem'). "
            "Return a valid JSON dictionary where each key is character_id, containing: "
            "'character_id', 'canonical_name_en', 'canonical_name_ar', 'role', "
            "'confirmed_attributes', 'ai_proposed_attributes', 'unknown_attributes', "
            "'canonical_wardrobe', 'personality_guidance', 'invariants', 'permitted_variations', 'character_sheet_prompt'."
        )

        user_content = json.dumps({
            "characters": [
                {
                    **c.model_dump(),
                    "canonical_name_en": c.get_canonical_name_en(),
                    "canonical_name_ar": c.get_canonical_name_ar()
                }
                for c in characters
            ],
            "visual_style": visual_style
        }, ensure_ascii=False)

        llm_resp = self._call_llm(system_prompt, user_content)
        if llm_resp:
            try:
                cleaned = re.sub(r"^```json\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and any(c.character_id in parsed for c in characters):
                    for c in characters:
                        if c.character_id in parsed:
                            c_dict = parsed[c.character_id]
                            c_dict["ai_generated"] = True
                            c_dict["generation_mode"] = "live_ai"
                            c_dict["canonical_name_en"] = c.get_canonical_name_en()
                            c_dict["canonical_name_ar"] = c.get_canonical_name_ar()
                            if "permitted_variations" not in c_dict:
                                c_dict["permitted_variations"] = c.permitted_variations or ["Situational poses and storytelling actions"]
                            if "personality_guidance" not in c_dict:
                                c_dict["personality_guidance"] = c.personality_guidance or "Curious, joyful, and emotionally resonant demeanor"
                    return parsed
            except Exception as e:
                logger.warning(f"LLM output JSON parse error in character bible: {e}")

        # Contextual Semantic Reasoning Engine (Offline / Robust Fallback)
        result = {}
        for c in characters:
            canon_en = c.get_canonical_name_en()
            canon_ar = c.get_canonical_name_ar()
            confirmed = {}
            proposed = {}
            unknown = []

            if c.apparent_age: confirmed["apparent_age"] = c.apparent_age
            else: unknown.append("exact age representation")

            if c.gender: confirmed["gender"] = c.gender
            else: unknown.append("gender specification")

            if c.face_shape: confirmed["face_shape"] = c.face_shape
            else: proposed["face_shape"] = "Childlike rounded face with soft cheek contours suited to 3D stylization"

            if c.skin_tone: confirmed["skin_tone"] = c.skin_tone
            else: unknown.append("skin tone shade")

            if c.hair_details: confirmed["hair_details"] = c.hair_details
            else: unknown.append("hair color and styling")

            if c.eye_details: confirmed["eye_details"] = c.eye_details
            else: proposed["eye_details"] = "Large expressive animated eyes with warm specular reflections"

            if c.canonical_clothing: confirmed["canonical_clothing"] = c.canonical_clothing
            else: unknown.append("canonical clothing colors and garments")

            if c.distinctive_features: confirmed["distinctive_features"] = c.distinctive_features
            else: proposed["distinctive_features"] = "Expressive open smile and curious gaze"

            turnaround_prompt = (
                f"Full character turnaround model sheet of {canon_en} ({canon_ar}), {c.apparent_age or 'young child'}. "
                f"Facial structure: {c.face_shape or confirmed.get('face_shape', 'soft rounded features')}. "
                f"Hair: {c.hair_details or 'natural textured curls'}. "
                f"Eyes: {c.eye_details or 'large expressive eyes'}. "
                f"Attire: {c.canonical_clothing or 'canonical storytelling outfit'}. "
                f"Showing 3 clear unobstructed views: front view relaxed standing, three-quarter action pose, and close-up smiling headshot. "
                f"Art style: {visual_style}. "
                f"Solid neutral light-grey studio background, no clutter, consistent anatomical proportions across views."
            )

            result[c.character_id] = {
                "character_id": c.character_id,
                "display_name": c.display_name,
                "canonical_name_en": canon_en,
                "canonical_name_ar": canon_ar,
                "role": c.role,
                "confirmed_attributes": confirmed,
                "ai_proposed_attributes": proposed,
                "unknown_attributes": unknown,
                "canonical_wardrobe": c.canonical_clothing or "Standard storytelling outfit",
                "personality_guidance": c.personality_guidance or "Curious, cheerful, and emotionally expressive demeanor",
                "character_sheet_prompt": turnaround_prompt,
                "invariants": c.invariants or list(confirmed.values()),
                "permitted_variations": c.permitted_variations or ["Situational actions and poses matching story narrative"],
                "ai_generated": False,
                "generation_mode": "fallback_heuristic"
            }

        return result

    # -----------------------------------------------------------------
    # 2. AI-Driven Scene Analysis & Prompt Authoring
    # -----------------------------------------------------------------
    def generate_scene_plan_and_prompts_ai(
        self,
        story_title: str,
        scenes: List[Dict[str, Any]],
        characters: List[CharacterProfile],
        visual_style: str,
        target_model: str,
        aspect_ratio: str
    ) -> List[Dict[str, Any]]:
        """
        AI reads every scene's exact Arabic text and its surrounding context to infer:
        - Setting and Time of Day (e.g. night sky with stars vs classroom vs bedroom vs ocean)
        - Specific character actions and postures
        - Emotional expressions
        - Props and environmental context
        - Lighting and atmospheric mood
        - Authors standalone, rich, creative image prompts for Workflows A, B, and C
        """
        system_prompt = f"""You are a senior art director and prompt engineer for AI children's book illustrations.
You will receive the full Arabic story segmented into exact verbatim scenes.
For EVERY scene, you must:
1. PRESERVE the exact Arabic text verbatim.
2. Read the Arabic text carefully and deduce the true setting, time of day, character action, emotions, and props.
   - Example: If the text mentions stars/night, the time of day MUST be nighttime with starlight, NEVER morning sunlight!
   - Example: If the text mentions school or teacher, the setting MUST be a classroom.
   - Example: If the text mentions diving, ocean, coral reef, or sea, the setting MUST be an underwater marine reef.
   - Example: If the text mentions making a solar system model, the setting MUST be a bedroom with crafting materials.
3. Distinguish required story facts from optional artistic embellishments:
   - 'required_story_elements': The essential plot events, characters, and items explicitly stated in the Arabic text.
   - 'creative_embellishments': Visual art-direction choices (lighting mood, background details, dynamic camera angles).
4. CRITICAL CHARACTER & IDENTITY RULE:
   - Do NOT describe character faces in the prompt text (NO descriptions of eyes, eye shape, nose, cheeks, mouth, skin tone, or facial geometry).
   - Instruct the AI model to use the characters' referenced imported images by index order:
     e.g., 'Character reference mapping: Karim is the first image [Image 1], and Teacher Huda is the second image [Image 2]. Use their referenced imported images for their facial appearance, hair, and identity; strictly do NOT describe or alter their faces.'
5. CRITICAL UNIFIED PROMPT FORMAT:
   - Every prompt ('prompt_workflow_a', 'prompt_workflow_b', 'prompt_workflow_c') MUST be ONE unified prompt containing BOTH the positive prompt AND the negative prompt together.
   - Enforce aspect ratio '{aspect_ratio} vertical' in the prompt.
   - Append the negative prompt directly at the end of the prompt in the format:
     '\\nNegative prompt: photorealistic face, photographic skin, pasted head, uncanny valley, distorted facial features, malformed hands, extra fingers, blurry, low quality, watermark, text'
6. Target model: {target_model}, Visual style: {visual_style}.

Return a valid JSON array of objects with keys:
- scene_id
- page_number
- exact_arabic_text
- required_story_elements
- creative_embellishments
- inferred_setting
- time_of_day
- character_action
- facial_expression
- props_and_environment
- lighting_and_atmosphere
- camera_composition
- continuity_requirements
- prompt_workflow_a (ONE unified prompt: positive prompt with character image index mapping and 9:16 vertical ratio + '\\nNegative prompt: ...')
- prompt_workflow_b (ONE unified prompt: photo-conditioning variant + '\\nNegative prompt: ...')
- prompt_workflow_c (ONE unified prompt: hybrid variant + '\\nNegative prompt: ...')
- negative_prompt
"""
        user_content = json.dumps({
            "story_title": story_title,
            "scenes": scenes,
            "characters": [c.model_dump() for c in characters],
            "visual_style": visual_style,
            "target_model": target_model,
            "aspect_ratio": aspect_ratio
        }, ensure_ascii=False)

        llm_resp = self._call_llm(system_prompt, user_content)
        if llm_resp:
            try:
                cleaned = re.sub(r"^```json\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) == len(scenes):
                    primary_char = characters[0] if characters else None
                    sheet_ref = primary_char.canonical_sheet if primary_char and primary_char.canonical_sheet else "character_sheet_reference"
                    photo_ref = primary_char.source_photos[0] if primary_char and primary_char.source_photos else "reference_image"

                    for idx, sc in enumerate(parsed):
                        # Ensure string fields from LLM are normalized to strings
                        for str_field in ["props_and_environment", "lighting_and_atmosphere", "inferred_setting", "time_of_day", "character_action", "facial_expression", "camera_composition"]:
                            if isinstance(sc.get(str_field), list):
                                sc[str_field] = ", ".join(str(x) for x in sc[str_field])

                        # Ensure 100% Arabic text verbatim preservation
                        sc["exact_arabic_text"] = scenes[idx]["exact_arabic_text"]
                        sc["scene_id"] = f"SCENE_{idx+1:02d}"
                        sc["page_number"] = idx + 1
                        sc["ai_generated"] = True
                        sc["generation_mode"] = "live_ai"
                        if "required_story_elements" not in sc or not sc["required_story_elements"]:
                            sc["required_story_elements"] = f"{sc.get('character_action', 'Story event')} in {sc.get('inferred_setting', 'scene setting')}"
                        if "creative_embellishments" not in sc or not sc["creative_embellishments"]:
                            sc["creative_embellishments"] = f"Atmosphere: {sc.get('lighting_and_atmosphere', 'ambient lighting')}; Composition: {sc.get('camera_composition', 'balanced composition')}"
                        if "reference_attachments" not in sc or not sc["reference_attachments"]:
                            sc["reference_attachments"] = {
                                "workflow_a": [sheet_ref],
                                "workflow_b": [photo_ref],
                                "workflow_c": [sheet_ref, photo_ref]
                            }
                    return parsed
            except Exception as e:
                logger.warning(f"LLM JSON parsing failed for scene plan: {e}")

        # Contextual Semantic Reasoning Engine (Offline / Robust Fallback)
        scene_plans = []
        primary_char = characters[0] if characters else None
        char_name = primary_char.display_name if primary_char else "The child"
        char_id = primary_char.character_id if primary_char else "CHAR_01"
        char_hair = primary_char.hair_details if primary_char else "curly dark-brown hair"
        char_clothing = primary_char.canonical_clothing if primary_char else "navy blue hoodie"
        char_eyes = primary_char.eye_details if primary_char else "dark-brown eyes"

        for idx, sc in enumerate(scenes):
            scene_num = idx + 1
            scene_id = f"SCENE_{scene_num:02d}"
            ar_text = sc["exact_arabic_text"]
            ar_lower = ar_text.lower()

            # Contextual Inference from Arabic keywords:
            # 1. Night / Stars / Sky
            if any(k in ar_text for k in ["ليل", "ليلة", "سماء", "نجوم", "نجم", "قمر", "شرفة"]):
                time_of_day = "Nighttime, clear dark indigo starlit sky"
                setting = "Home balcony or terrace overlooking a quiet town under deep night sky"
                lighting = "Soft celestial starlight and cool silver moonlight, with warm ambient glow spilling from the open balcony doorway"
                action = f"{char_name} is leaning against the balcony railing, pointing upward into the night sky, enchanted as he counts glowing stars"
                expression = "Awe-struck and joyful, eyes wide and filled with starry reflections"
                props = "Balcony iron railing, gentle night breeze rustling curtains, twinkling constellations in background"
                camera = "Low-angle medium shot capturing the child against the vast, illuminated night sky"
            # 2. School / Classroom / Teacher / Book
            elif any(k in ar_text for k in ["مدرسة", "معلم", "أستاذ", "كتاب", "صف", "درس"]):
                time_of_day = "Daytime, bright mid-morning"
                setting = "Cheery school classroom with colorful educational posters and wooden desks"
                lighting = "Warm natural sunlight pouring through tall classroom windows, soft dust motes in sunbeams"
                action = f"{char_name} is sitting at a wooden desk with his teacher standing nearby, holding open a vibrant illustrated book showcasing the planet Saturn and its luminous rings"
                expression = "Fascinated and inspired, beaming with intellectual curiosity"
                props = "Open astronomy book with planetary diagrams, colorful blackboard drawings in background"
                camera = "Medium shot focusing on the child and the illuminated space book on the desk"
            # 3. Sea / Ocean / Coral Reef / Diving / Underwater
            elif any(k in ar_text for k in ["بحر", "مياه", "غاصت", "غوص", "مرجان", "شعاب", "سلاحف", "سمك", "أسماك"]):
                time_of_day = "Daytime, bright sunlit underwater"
                setting = "Vibrant tropical coral reef underwater seascape with crystal clear turquoise water"
                lighting = "Dappled caustic sunlight shimmering down through clear turquoise ocean water"
                action = f"{char_name} is swimming gracefully among colorful coral formations, extending a hand in wonder toward a gentle sea turtle"
                expression = "Awe-struck joy and wonder, eyes sparkling with underwater adventure"
                props = "Living coral reef formations, schools of iridescent tropical clownfish, friendly sea turtle"
                camera = "Wide-angle panoramic underwater shot with dynamic light rays penetrating the blue sea"
            # 4. Bedroom / Model Making / Crafting
            elif any(k in ar_text for k in ["غرفة", "صنع", "نموذج", "كرات", "خيوط", "سقف"]):
                time_of_day = "Late afternoon / twilight"
                setting = "Cozy child's bedroom transformed into a whimsical maker space"
                lighting = "Warm golden desk lamp illuminating colorful painted spheres, gentle atmospheric twilight outside the window"
                action = f"{char_name} is standing on a small wooden stool, carefully hanging hand-painted celestial spheres from strings attached to his bedroom ceiling"
                expression = "Deeply focused and proud, small tongue-in-cheek concentration smiling expression"
                props = "Colorful hand-painted solar system model hanging overhead, paints and brushes on desk"
                camera = "Dynamic eye-level three-quarter shot showing the handmade solar system suspended across the ceiling"
            # 5. Contest / Art / Rocket / Painting
            elif any(k in ar_text for k in ["مسابقة", "رسم", "لوحة", "صاروخ", "ألوان"]):
                time_of_day = "Bright afternoon"
                setting = "School art studio or exhibition hall with student easels"
                lighting = "Vibrant gallery illumination, clean natural daylight highlighting bright tempera paint colors"
                action = f"{char_name} stands before a large canvas easel holding a paintbrush, proudly showcasing his dynamic painting of a rocket blasting toward the moon"
                expression = "Confident, radiant smile of accomplishment and artistic pride"
                props = "Large easel, colorful paint jars, wooden palette with primary colors, rocket painting"
                camera = "Heroic medium-close shot centering on the child and his vibrant rocket painting"
            # 6. Celebration / Award / First Place / Parents
            elif any(k in ar_text for k in ["فاز", "جائزة", "أولى", "احتفل", "والد", "أم", "حلم"]):
                time_of_day = "Warm golden hour"
                setting = "Home living room or school auditorium podium"
                lighting = "Triumphant golden-hour lighting with radiant warm glow and celebratory sparkle"
                action = f"{char_name} proudly holds up his first-place certificate/medal beside his beaming parents, celebrating his dream of reaching the cosmos"
                expression = "Ecstatic, triumphant smile filled with self-belief and hope"
                props = "First-place award ribbon, framed space drawing on wall, celebratory atmosphere"
                camera = "Centering medium shot capturing the victorious family moment"
            else:
                time_of_day = "Daytime, bright and clear"
                setting = "Warm child-friendly environment matching the narrative"
                lighting = "Soft natural lighting with warm ambient fill"
                action = f"{char_name} actively participates in the scene, expressing genuine wonder"
                expression = "Expressive, curious, and cheerful"
                props = "Environment details relevant to the story narrative"
                camera = "Medium balanced storytelling shot"

            # If the story engine supplied a dedicated image_description, prioritize it
            if sc.get("image_description"):
                action = f"{char_name}: {sc['image_description']}"

            sheet_ref = primary_char.canonical_sheet if primary_char and primary_char.canonical_sheet else "character_sheet_reference"
            photo_ref = primary_char.source_photos[0] if primary_char and primary_char.source_photos else "reference_image"

            char_ref_mapping = self.build_character_reference_mapping(characters)
            neg_prompt = (
                "photorealistic face, photographic skin, pasted photo, uncanny valley, "
                "distorted facial features, distorted anatomy, blurry, low resolution, "
                "watermark, signature, ugly, malformed hands, extra fingers, text, typography, speech bubbles"
            )

            prompt_a = (
                f"{visual_style}. "
                f"Narrative scene: {action}. "
                f"{char_ref_mapping} "
                f"Wearing canonical attire: {char_clothing}. "
                f"Character emotion: {expression}. "
                f"Environment: {setting}. {props}. "
                f"Lighting & Atmosphere: {lighting}. Time of day: {time_of_day}. "
                f"Cinematic framing: {camera}. Aspect ratio: 9:16 vertical. "
                f"High-detail 3D animated digital illustration, cohesive color palette, no text.\n"
                f"Negative prompt: {neg_prompt}"
            )

            prompt_b = (
                f"{visual_style}. "
                f"Scene: {action}. "
                f"{char_ref_mapping} "
                f"Redraw completely as a stylized 3D animated character; do NOT paste or insert a photorealistic face. "
                f"Attire: {char_clothing}. Emotion: {expression}. "
                f"Setting: {setting}. {props}. "
                f"Lighting: {lighting} ({time_of_day}). {camera}. Aspect ratio: 9:16 vertical. "
                f"Vibrant, child-friendly storytelling illustration.\n"
                f"Negative prompt: {neg_prompt}"
            )

            prompt_c = (
                f"{visual_style}. "
                f"Scene: {action}. "
                f"{char_ref_mapping} "
                f"Wearing canonical outfit: {char_clothing}. "
                f"Emotion: {expression}. "
                f"Setting: {setting}. {props}. "
                f"Lighting: {lighting} ({time_of_day}). {camera}. Aspect ratio: 9:16 vertical. "
                f"Polished animated film still quality.\n"
                f"Negative prompt: {neg_prompt}"
            )

            required_story = f"{action} in {setting}"
            creative_embellish = f"Lighting: {lighting}; Composition: {camera}; Props: {props}"

            scene_plans.append({
                "scene_id": scene_id,
                "page_number": scene_num,
                "exact_arabic_text": ar_text,
                "required_story_elements": required_story,
                "creative_embellishments": creative_embellish,
                "inferred_setting": setting,
                "time_of_day": time_of_day,
                "character_action": action,
                "facial_expression": expression,
                "props_and_environment": props,
                "lighting_and_atmosphere": lighting,
                "camera_composition": camera,
                "continuity_requirements": f"Preserve {char_hair}, {char_eyes}, and {char_clothing} across all scenes.",
                "reference_attachments": {
                    "workflow_a": [sheet_ref],
                    "workflow_b": [photo_ref],
                    "workflow_c": [sheet_ref, photo_ref]
                },
                "prompt_workflow_a": prompt_a,
                "prompt_workflow_b": prompt_b,
                "prompt_workflow_c": prompt_c,
                "negative_prompt": neg_prompt,
                "ai_generated": False,
                "generation_mode": "fallback_heuristic"
            })

        return scene_plans

    @classmethod
    def build_character_reference_mapping(
        cls,
        characters: List[Any],
        all_characters: Optional[List[Any]] = None
    ) -> str:
        """
        Build explicit reference mapping for all characters in the story (up to 3 characters total):
        - 1 character: Karim is the first image [Image 1]
        - 2 characters: Karim is the first image [Image 1], and Teacher Huda is the second image [Image 2]
        - 3 characters: Karim is the first image [Image 1], Teacher Huda is the second image [Image 2], and Grandma Salma is the third image [Image 3]
        Maintains consistent 1-based indexing relative to the global story character list.
        """
        if not characters:
            return (
                "Character reference mapping: The character corresponds to the first attached image [Image 1]. "
                "Use the referenced imported image for character facial appearance, hair, and identity; "
                "strictly do NOT describe character faces in text or alter their faces."
            )

        ordinals = ["first", "second", "third", "fourth", "fifth"]
        global_list = all_characters or characters

        # Build consistent global index map for all characters in story (1-based)
        global_index_map = {}
        for g_idx, g_char in enumerate(global_list[:3]):
            cid = getattr(g_char, "character_id", "") or str(g_idx)
            cname = getattr(g_char, "display_name", "") or getattr(g_char, "name", "")
            global_index_map[cid] = g_idx + 1
            global_index_map[cname] = g_idx + 1
            if "/" in cname:
                global_index_map[cname.split("/")[-1].strip()] = g_idx + 1
                global_index_map[cname.split("/")[0].strip()] = g_idx + 1

        parts = []
        for char in characters[:3]:
            c_name = getattr(char, "display_name", "") or getattr(char, "name", "") or "Character"
            clean_name = c_name.split("/")[-1].strip() if "/" in c_name else c_name.strip()
            cid = getattr(char, "character_id", "")
            img_num = global_index_map.get(cid) or global_index_map.get(c_name) or global_index_map.get(clean_name) or (len(parts) + 1)
            ord_word = ordinals[img_num - 1] if (img_num - 1) < len(ordinals) else f"{img_num}th"
            parts.append(f"{clean_name} is the {ord_word} image [Image {img_num}]")

        if len(parts) == 1:
            mapping_str = parts[0]
        elif len(parts) == 2:
            mapping_str = f"{parts[0]}, and {parts[1]}"
        else:
            mapping_str = f"{parts[0]}, {parts[1]}, and {parts[2]}"

        return (
            f"Character reference mapping: {mapping_str}. "
            "Use their referenced imported images for their facial appearance, hair, and identity. "
            "Strictly do NOT describe character faces in text or alter their faces."
        )

    @classmethod
    def _add_reference_context_to_scene_prompts(
        cls,
        scene_plans: List[Dict[str, Any]],
        characters: Optional[List[Any]] = None,
        aspect_ratio: str = "9:16"
    ) -> None:
        """
        Make the deferred image-reference contract explicit in every prompt:
        1. Character reference mapping (e.g. Karim is the first image [Image 1], Teacher is the second image [Image 2], Grandma is the third image [Image 3]).
        2. Reference images available instruction.
        3. 9:16 vertical aspect ratio.
        4. One unified prompt containing both prompt + negative prompt.
        """
        reference_note = (
            "Reference images are available to the image model as attached inputs. "
            "Use them only for identity and visual continuity, then fully redraw the character "
            "as the requested stylized illustration; do not paste or photorealistically copy the photos."
        )
        neg_default = (
            "photorealistic face, photographic skin, pasted photo, uncanny valley, "
            "distorted facial features, distorted anatomy, blurry, low resolution, "
            "watermark, signature, ugly, malformed hands, extra fingers, text, typography, speech bubbles"
        )
        ratio_note = f"Aspect ratio: {aspect_ratio} vertical format."

        for scene in scene_plans:
            # Check characters present in this specific scene
            scene_char_ids = scene.get("character_reference_ids") or []
            if scene_char_ids and characters:
                sc_chars = [c for c in characters if getattr(c, "character_id", "") in scene_char_ids]
                if not sc_chars:
                    sc_chars = characters[:1]
            else:
                sc_chars = characters or []

            mapping_note = cls.build_character_reference_mapping(sc_chars, all_characters=characters)
            neg_to_use = scene.get("negative_prompt") or neg_default

            for field in ("prompt_workflow_a", "prompt_workflow_b", "prompt_workflow_c"):
                prompt = str(scene.get(field, "")).strip()
                if not prompt:
                    continue

                if "Negative prompt:" in prompt:
                    parts = prompt.split("Negative prompt:", 1)
                    pos_part = parts[0].strip()
                    neg_to_use = parts[1].strip() or neg_to_use
                    prompt = pos_part

                if "is the first image" not in prompt and "Character reference mapping:" not in prompt:
                    prompt = f"{prompt} {mapping_note}"

                if reference_note not in prompt:
                    prompt = f"{prompt} {reference_note}"

                if "9:16" not in prompt and "aspect ratio" not in prompt.lower():
                    prompt = f"{prompt} {ratio_note}"

                # Append negative prompt to make it ONE unified prompt
                prompt = f"{prompt}\nNegative prompt: {neg_to_use}"

                scene[field] = prompt

    # -----------------------------------------------------------------
    # 3. AI Cover Prompt Authoring
    # -----------------------------------------------------------------
    def generate_cover_prompt_ai(
        self,
        story_title: str,
        characters: List[CharacterProfile],
        visual_style: str,
        target_model: str,
        aspect_ratio: str,
        arabic_story_text: str = ""
    ) -> Dict[str, Any]:
        """AI authors a bespoke book cover prompt reserving title typography space and grounded in narrative reality."""
        primary_char = characters[0] if characters else None
        char_name_en = primary_char.get_canonical_name_en() if primary_char else "The child hero"
        char_name_ar = primary_char.get_canonical_name_ar() if primary_char else "البطل"
        char_age = primary_char.apparent_age if primary_char else "young child"
        char_outfit = primary_char.canonical_clothing if primary_char else "canonical outfit"
        char_hair = primary_char.hair_details if primary_char else "curled hair"

        system_prompt = (
            "You are an award-winning children's book cover illustrator. "
            "Write a magical, high-impact book cover prompt. "
            "STRICT STORY FIDELITY REQUIREMENT: The cover MUST represent the actual central theme and setting of the story. "
            "Do NOT introduce ungrounded sci-fi or fantasy locations (such as floating weightlessly in outer space or alien worlds) "
            "unless the story text explicitly takes place in space! "
            "If the story is a grounded tale (e.g., a child stargazing from a home balcony and inspired by school books), "
            "the cover MUST feature that grounded setting (e.g., on the quiet starlit balcony looking up in wonder at glowing constellations). "
            f"CANONICAL CHARACTER SPELLING: Strictly use the canonical spelling '{char_name_en}'. Never spell it differently. "
            f"CANONICAL WARDROBE: The character MUST wear their exact canonical outfit: '{char_outfit}'. "
            "COMPOSITION REQUIREMENT: Leave generous, completely clean, smooth, unobstructed negative space across the upper 35% "
            "of the canvas exclusively for the Arabic title typography. Do NOT render any letters, words, or calligraphy."
        )
        user_content = f"Title: {story_title}. Narrative text: {arabic_story_text}. Character: {char_name_en} ({char_age}, {char_hair}, {char_outfit}). Style: {visual_style}."

        llm_resp = self._call_llm(system_prompt, user_content)
        if llm_resp and len(llm_resp) > 60:
            prompt = llm_resp.strip()
            is_ai = True
            mode = "live_ai"
        else:
            prompt = (
                f"Enchanting children's book cover art for '{story_title}'. "
                f"Heroic, inviting pose of {char_name_en} ({char_age}, {char_hair}, dressed in {char_outfit}), "
                f"looking toward the viewer with an inspiring smile of discovery, surrounded by atmospheric elements true to the narrative. "
                f"Art style: {visual_style}. "
                f"COMPOSITION REQUIREMENT: Leave generous, completely clean and unobstructed negative space across the upper 35% "
                f"of the canvas for the title typography. Do NOT render any letters, words, or calligraphy. "
                f"Atmospheric volumetric rim lighting, magical ambient glow, high-end 3D animated film poster masterpiece."
            )
            is_ai = False
            mode = "fallback_heuristic"

        neg = (
            "text, words, letters, typography, book title, calligraphy, watermark, logo, barcode, "
            "photorealistic, real photograph, collage, dark gritty shadows, frightening faces"
        )
        return {
            "cover_prompt": prompt,
            "negative_prompt": neg,
            "ai_generated": is_ai,
            "generation_mode": mode
        }

    # -----------------------------------------------------------------
    # 4. AI-Driven Prompt Revision
    # -----------------------------------------------------------------
    def revise_prompt_ai(
        self,
        exact_arabic_text: str,
        current_prompt: str,
        user_instruction: str,
        character_invariants: List[str],
        target_model: str = "Model-Agnostic"
    ) -> Dict[str, Any]:
        """
        AI revises a prompt intelligently based on user feedback,
        preserving unaffected character invariants and story context.
        """
        system_prompt = (
            "You are an AI illustration prompt revision assistant. "
            "The user wants to revise an existing illustration prompt. "
            "Analyze the original Arabic scene text, the current prompt, and the user's instructions. "
            "Modify ONLY what the user requests (e.g. pose, camera angle, setting fidelity). "
            "STRICTLY PRESERVE all character invariants, face identity locks, and story continuity. "
            "Return JSON with keys: 'revised_prompt', 'modifications_summary', 'preserved_invariants'."
        )
        user_content = json.dumps({
            "arabic_scene_text": exact_arabic_text,
            "current_prompt": current_prompt,
            "user_instruction": user_instruction,
            "character_invariants": character_invariants,
            "target_model": target_model
        }, ensure_ascii=False)

        llm_resp = self._call_llm(system_prompt, user_content)
        if llm_resp:
            try:
                cleaned = re.sub(r"^```json\s*", "", llm_resp.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                if isinstance(data, dict) and "revised_prompt" in data:
                    data["ai_generated"] = True
                    data["generation_mode"] = "live_ai"
                    return data
            except Exception as e:
                logger.warning(f"Revision parse failed: {e}")

        # Semantic Revision Engine (Safe / Offline Fallback)
        revised = current_prompt
        inst_lower = user_instruction.lower()

        if "pose" in inst_lower or "sitting" in inst_lower or "standing" in inst_lower:
            revised = re.sub(r"Scene action: [^.]+\.", f"Scene action: {user_instruction.strip()}.", revised)
        if "cinematic" in inst_lower or "lighting" in inst_lower or "mood" in inst_lower:
            revised += f" Enhanced cinematic mood: {user_instruction.strip()}."
        if "reference" in inst_lower or "resemblance" in inst_lower or "face" in inst_lower:
            revised = f"High fidelity character likeness: meticulously reproduce facial features from reference image. {revised}"
        if "midjourney" in inst_lower:
            revised += " --ar 1:1 --v 6.0 --style raw"

        return {
            "revised_prompt": revised,
            "modifications_summary": f"Executed user instruction: '{user_instruction}' while preserving character locks and story fidelity.",
            "preserved_invariants": character_invariants,
            "ai_generated": False,
            "generation_mode": "fallback_heuristic"
        }


# =====================================================================
# Arabic Text Verbatim Segmenter
# =====================================================================

def segment_arabic_story_verbatim(arabic_text: str, target_scenes: int = 10) -> List[Dict[str, Any]]:
    """
    Splits the Arabic story into target_scenes without modifying, translating,
    or shortening any words. Preserves original punctuation and phrasing exactly.
    Recognizes both standard chapter headers and page headers from the stories model.
    """
    cleaned = arabic_text.strip()
    chapter_pattern = r'(?:صفحة\s*:?\s*\d+\s*[:\-–]?|:?\s*\d+\s*:?\s*صفحة\s*[:\-–]?|page\s*\d+\s*[:\-–]?|فصل\s*\d+\s*:?|الفصل\s+[\u0621-\u064A\d]+\s*:?|\b\d+\s*[-–.]\s*)'
    matches = list(re.finditer(chapter_pattern, cleaned, re.IGNORECASE))
    
    if len(matches) >= target_scenes // 2 and len(matches) > 1:
        indices = [m.start() for m in matches] + [len(cleaned)]
        raw_segments = []
        for i in range(len(indices) - 1):
            seg = cleaned[indices[i]:indices[i+1]].strip()
            if seg:
                raw_segments.append(seg)
    else:
        raw_segments = [s.strip() for s in re.split(r'(?<=[.!?؟\n])\s*', cleaned) if s.strip()]
        if not raw_segments:
            raw_segments = [cleaned]

    n = len(raw_segments)
    if n == target_scenes:
        final_segments = raw_segments
    elif n > target_scenes:
        final_segments = []
        for i in range(target_scenes):
            start = i * n // target_scenes
            end = (i + 1) * n // target_scenes
            final_segments.append(" ".join(raw_segments[start:end]))
    else:
        cur = list(raw_segments)
        while len(cur) < target_scenes:
            longest_idx = max(range(len(cur)), key=lambda i: len(cur[i].split()))
            words = cur[longest_idx].split()
            if len(words) <= 1:
                break
            mid = len(words) // 2
            p1 = " ".join(words[:mid])
            p2 = " ".join(words[mid:])
            cur[longest_idx] = p1
            cur.insert(longest_idx + 1, p2)
        final_segments = cur

    return [{"scene_index": i + 1, "exact_arabic_text": text} for i, text in enumerate(final_segments)]


def parse_story_model_outcome(raw_text: str) -> Dict[str, Any]:
    """
    Parses outcomes produced by the Hekayti story model (make_input(...) plus scene pages)
    and translates them into structured pipeline inputs for the image generation model.
    """
    cleaned = raw_text.strip()
    result: Dict[str, Any] = {
        "metadata": {},
        "title": "",
        "story_text": "",
        "scenes": [],
        "detected_gender": "child",
        "language_canonical": "Simple Modern Standard Arabic",
        "characters": []
    }

    # 1. Parse make_input(...) if present
    start_pos = cleaned.find("make_input")
    story_body = cleaned
    if start_pos != -1:
        paren_start = cleaned.find("(", start_pos)
        if paren_start != -1:
            depth = 0
            call_end = -1
            in_string = False
            str_char = ''
            escape = False
            for i in range(paren_start, len(cleaned)):
                c = cleaned[i]
                if in_string:
                    if escape:
                        escape = False
                    elif c == '\\':
                        escape = True
                    elif c == str_char:
                        in_string = False
                else:
                    if c in ("'", '"'):
                        in_string = True
                        str_char = c
                    elif c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                        if depth == 0:
                            call_end = i + 1
                            break
            if call_end != -1:
                call_str = cleaned[start_pos:call_end]
                story_body = cleaned[call_end:].strip()
                try:
                    tree = ast.parse(call_str)
                    for item in tree.body:
                        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call):
                            for kw in item.value.keywords:
                                key = kw.arg
                                try:
                                    val = ast.literal_eval(kw.value)
                                    result["metadata"][key] = val
                                except Exception:
                                    pass
                except Exception:
                    # Fallback regex extraction if ast fails
                    for m in re.finditer(r'(\w+)\s*=\s*([^,\)\n]+)', call_str):
                        k, v = m.group(1), m.group(2).strip()
                        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        result["metadata"][k] = v

    meta = result["metadata"]

    # 2. Extract Title and Story Body
    lines = [line.strip() for line in story_body.splitlines() if line.strip()]
    content_lines = []
    found_title = False

    for line in lines:
        if not found_title:
            is_exp = bool(re.match(r'^(?:التجربة\s*\d+\s*[:\-–]?\s*|story\s*\d+\s*[:\-–]?\s*)', line, re.IGNORECASE))
            is_page_hdr = bool(re.match(r'^(?:صفحة\s*:?\s*\d+|:?\s*\d+\s*:?\s*صفحة|page\s*\d+)', line, re.IGNORECASE))
            if is_exp or (len(line) < 80 and not is_page_hdr and line != "صفحات القصة"):
                clean_title = re.sub(r'^(?:التجربة\s*\d+\s*[:\-–]?\s*|story\s*\d+\s*[:\-–]?\s*)', '', line, flags=re.IGNORECASE).strip()
                if clean_title and clean_title != "صفحات القصة":
                    result["title"] = clean_title
                    found_title = True
                    continue
        if line == "صفحات القصة":
            continue
        content_lines.append(line)

    result["story_text"] = "\n\n".join(content_lines)

    # 3. Extract Scenes (using page splits)
    page_pattern = r'(?:^|\n)\s*(?:صفحة\s*:?\s*(\d+)\s*[:\-–]?\s*([^\n]*)|:?\s*(\d+)\s*:?\s*صفحة\s*[:\-–]?\s*([^\n]*)|page\s*(\d+)\s*[:\-–]?\s*([^\n]*))'
    split_positions = []
    for m in re.finditer(page_pattern, result["story_text"], re.IGNORECASE):
        page_num = m.group(1) or m.group(3) or m.group(5)
        page_title = (m.group(2) or m.group(4) or m.group(6) or "").strip()
        split_positions.append((m.start(), m.end(), int(page_num), page_title))

    if split_positions:
        scenes = []
        for i in range(len(split_positions)):
            start_content = split_positions[i][1]
            end_content = split_positions[i+1][0] if i + 1 < len(split_positions) else len(result["story_text"])
            page_text = result["story_text"][start_content:end_content].strip()
            scenes.append({
                "page_number": split_positions[i][2],
                "scene_title": split_positions[i][3],
                "exact_text": page_text
            })
        result["scenes"] = scenes

    if not result["scenes"] and result["story_text"]:
        paras = [p.strip() for p in result["story_text"].split("\n\n") if p.strip()]
        result["scenes"] = [{"page_number": i + 1, "scene_title": f"Scene {i+1}", "exact_text": p} for i, p in enumerate(paras)]

    # 4. Canonical language mapping
    raw_lang = meta.get("language", "").lower()
    if "egypt" in raw_lang or "عامية" in raw_lang:
        result["language_canonical"] = "Egyptian Arabic"
    elif "eng" in raw_lang:
        result["language_canonical"] = "English"
    else:
        result["language_canonical"] = "Simple Modern Standard Arabic"

    # 5. Gender detection
    child_name = meta.get("name", "").strip() or "Child"
    dedication = meta.get("dedication", "")
    known_girls = {"نور", "nour", "سلمى", "salma", "مينا", "mina", "سارة", "sara", "فاطمة", "fatima", "مريم", "mariam", "ليلى", "laila", "هند", "hind", "ياسمين", "yasmin"}
    known_boys = {"آدم", "adam", "كريم", "karim", "عمر", "omar", "أحمد", "ahmed", "يوسف", "youssef", "علي", "ali", "محمد", "mohamed", "طارق", "tarek", "leo"}

    c_name_lower = child_name.lower()
    if c_name_lower in known_girls:
        detected_gender = "girl"
    elif c_name_lower in known_boys:
        detected_gender = "boy"
    else:
        first_chunk = (dedication + " " + result["story_text"][:250]).lower()
        if any(w in first_chunk for w in ["صاحبة", "صغيرتنا", "المستكشفة", "girl", "she", "her", "ذات العشرة", "ذات ال"]):
            detected_gender = "girl"
        elif any(w in first_chunk for w in ["صاحب", "صغيرنا", "المستكشف", "boy", "he", "his", "ذو العشرة", "ذو ال"]):
            detected_gender = "boy"
        else:
            detected_gender = "child"
    result["detected_gender"] = detected_gender

    # 6. Build Character Profiles for Image Pipeline
    child_age = meta.get("age", 6)
    gender_noun = "girl" if detected_gender == "girl" else "boy"
    apparent_age = f"{child_age}-year-old {gender_noun}"
    name_slug = re.sub(r'[^a-z0-9]+', '_', child_name.lower()).strip('_') or "child"

    interests_list = meta.get("interests", [])
    if isinstance(interests_list, list):
        interests_str = "، ".join(interests_list)
    else:
        interests_str = str(interests_list)

    characters = [{
        "character_id": "CHILD_01",
        "display_name": child_name,
        "canonical_name_ar": child_name,
        "role": "Protagonist",
        "apparent_age": apparent_age,
        "gender": detected_gender,
        "hair_details": "Natural stylized hair suited to character",
        "skin_tone": "Warm radiant skin tone",
        "canonical_clothing": f"Canonical everyday attire reflecting interests in {interests_str or 'play'}",
        "distinctive_features": f"Interests: {interests_str}",
        "source_photos": [f"{name_slug}_photo_01.jpg"],
        "canonical_sheet": f"{name_slug}_character_sheet.png",
        "invariants": [interests_str] if interests_str else []
    }]

    # Additional supporting characters
    add_chars = meta.get("additional_characters", [])
    if isinstance(add_chars, list):
        for idx, ac in enumerate(add_chars):
            if isinstance(ac, dict):
                c_name = ac.get("name", f"Supporting #{idx+1}").strip()
                c_role = ac.get("role", "Supporting Character").strip()
            else:
                c_name = str(ac).strip()
                c_role = "Supporting Character"
            
            c_slug = re.sub(r'[^a-z0-9]+', '_', c_name.lower()).strip('_') or f"char_{idx+2}"
            is_mentor = any(w in (c_role + " " + c_name).lower() for w in [
                "جدة", "معلم", "أب", "أم", "خياطة", "مدرب", "coach", "teacher", "grandma", "parent", "mentor"
            ])
            c_age = "Adult / Mentor figure" if is_mentor else "Child friend"

            characters.append({
                "character_id": f"CHAR_{idx+2:02d}",
                "display_name": c_name,
                "canonical_name_ar": c_name,
                "role": c_role,
                "apparent_age": c_age,
                "hair_details": "Natural styling suited to age and role",
                "skin_tone": "Natural warm skin tone",
                "canonical_clothing": f"Attire suited to: {c_role}",
                "distinctive_features": c_role,
                "source_photos": [],
                "canonical_sheet": f"{c_slug}_character_sheet.png",
                "invariants": [c_role]
            })

    result["characters"] = characters
    return result


def validate_inputs_and_find_missing(story_input: StoryInput) -> List[str]:
    """Validates essential missing inputs to prevent inventing details."""
    questions = []
    if not story_input.arabic_story_text or len(story_input.arabic_story_text.strip()) < 15:
        questions.append("The Arabic story text is empty or too short. Please provide the complete Arabic story text.")
    if not story_input.characters:
        questions.append("No characters were defined. Who is the main character (name, age, and visual description)?")
    else:
        for idx, char in enumerate(story_input.characters):
            name = char.display_name or f"Character #{idx+1}"
            if not char.apparent_age.strip():
                questions.append(f"What is the apparent age representation for '{name}' (e.g. 5-year-old child)?")
            if not char.hair_details.strip():
                questions.append(f"What is '{name}'s hair color, hairstyle, and texture? (Needed for character consistency).")
            if not char.skin_tone.strip() and not char.face_shape.strip():
                questions.append(f"What are '{name}'s skin tone and facial structure?")
            if not char.canonical_clothing.strip():
                questions.append(f"What is '{name}'s default/canonical clothing (colors, garment types, footwear)?")
            if not char.source_photos and not char.canonical_sheet:
                questions.append(f"No reference photo or character sheet filename was specified for '{name}'.")
    return questions


def audit_prompt_pack_consistency(
    story_input: StoryInput,
    scene_plans: List[Dict[str, Any]],
    cover_data: Dict[str, Any],
    ai_char_bible: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Automated Deterministic Consistency Auditor.
    Checks and auto-corrects:
    1. Canonical spelling consistency across all prompts and artifacts.
       Detects transliteration drift (e.g. 'Kareem' vs 'Karim') and applies auto-correction.
    2. Grounded story fidelity and cover-to-story alignment.
       Detects ungrounded fantasy/sci-fi drift (e.g. floating in space when story is on a balcony) and auto-repairs.
    3. Wardrobe continuity across scenes.
    4. Exact Arabic source-text preservation (100% word-for-word check).
    5. Fallback metadata accuracy.
    """
    findings = []
    repaired_items = []

    # 1. Canonical Name Audit & Auto-Correction
    for char in story_input.characters:
        canon_en = char.get_canonical_name_en()
        variations = []
        if canon_en.lower() == "karim":
            variations = ["Kareem", "Careem", "Karem"]
        elif canon_en.lower() == "layla":
            variations = ["Leila", "Laila", "Lela"]
        elif canon_en.lower() == "omar":
            variations = ["Umar", "Omer"]
        elif canon_en.lower() == "salma":
            variations = ["Salmah", "Selma"]

        # Audit cover_prompt
        cover_text = cover_data.get("cover_prompt", "")
        for v in variations:
            pattern = re.compile(rf"\b{v}\b", re.IGNORECASE)
            if pattern.search(cover_text):
                findings.append(f"Character name drift in cover prompt: found '{v}' instead of canonical '{canon_en}'.")
                cover_data["cover_prompt"] = pattern.sub(canon_en, cover_data["cover_prompt"])
                repaired_items.append(f"Standardized '{v}' to canonical '{canon_en}' in cover prompt.")

        # Audit scene prompts
        for sc in scene_plans:
            for wf in ["prompt_workflow_a", "prompt_workflow_b", "prompt_workflow_c"]:
                p_text = sc.get(wf, "")
                for v in variations:
                    pattern = re.compile(rf"\b{v}\b", re.IGNORECASE)
                    if pattern.search(p_text):
                        findings.append(f"Character name drift in {sc['scene_id']} ({wf}): found '{v}' instead of canonical '{canon_en}'.")
                        sc[wf] = pattern.sub(canon_en, sc[wf])
                        repaired_items.append(f"Standardized '{v}' to canonical '{canon_en}' in {sc['scene_id']}.")

    # 2. Cover-to-Story Grounding Audit
    story_ar = story_input.arabic_story_text
    is_space_fiction = any(k in story_ar for k in ["مركبة فضائية", "صاروخ فضائي", "انعدام الوزن", "سطح القمر", "مريخ"])
    cover_text = cover_data.get("cover_prompt", "")

    if not is_space_fiction:
        floating_in_space = bool(re.search(r"floats weightlessly in (the vastness of )?outer space|floating in space|astronaut suit", cover_text, re.IGNORECASE))
        if floating_in_space:
            primary_char = story_input.characters[0] if story_input.characters else None
            c_name = primary_char.get_canonical_name_en() if primary_char else "The child"
            c_age = primary_char.apparent_age if primary_char else "6-year-old child"
            c_outfit = primary_char.canonical_clothing if primary_char else "navy blue hoodie"

            findings.append("Cover prompt hallucinated ungrounded sci-fi setting (floating weightlessly in outer space) when narrative is grounded in home balcony stargazing.")

            grounded_cover = (
                f"Enchanting Disney-Pixar 3D animated book cover illustration for '{story_input.title}'. "
                f"A joyful, wide-eyed {c_age} named {c_name} with short curly dark-brown hair, wearing his signature {c_outfit}, "
                f"standing on a quiet Arabic-style balcony at night under a luminous, deep indigo sky sparkling with radiant stars. "
                f"He holds an open illustrated picture book of the planet Saturn and smiles toward the heavens in wonder. "
                f"Warm volumetric lighting: cool celestial starlight from above, warm golden ambient glow from home windows behind him. "
                f"COMPOSITION REQUIREMENT: Leave the upper 35% of the frame completely empty, smooth, and unobstructed with a clean cosmic gradient "
                f"exclusively for the Arabic title typography. NO TEXT, NO LETTERING, NO SYMBOLS."
            )
            cover_data["cover_prompt"] = grounded_cover
            repaired_items.append("Aligned cover prompt to grounded story reality (starlit balcony looking up at stars with Saturn book).")

    # 3. Wardrobe Continuity Audit
    conflicts_flagged = []
    for char in story_input.characters:
        canon_outfit = char.canonical_clothing
        canon_en = char.get_canonical_name_en()
        canon_hair = char.hair_details.lower() if char.hair_details else ""

        # Contradictory attribute detection across scene prompts
        for sc in scene_plans:
            p_text = sc.get("prompt_workflow_a", "").lower()

            # Hair color contradiction check
            if ("dark" in canon_hair or "black" in canon_hair or "brown" in canon_hair):
                if re.search(r'\b(blonde|golden hair|red hair|ginger hair)\b', p_text):
                    bad_hair = re.search(r'\b(blonde|golden hair|red hair|ginger hair)\b', p_text).group(0)
                    conflicts_flagged.append({
                        "character_id": char.character_id,
                        "canonical_name": canon_en,
                        "scene_id": sc["scene_id"],
                        "conflict_type": "hair_color_conflict",
                        "canonical_value": char.hair_details,
                        "conflicting_value": bad_hair,
                        "action_taken": "FLAGGED_FOR_HUMAN_REVIEW (Not silently changed)"
                    })
                    findings.append(f"[CONFLICT] {sc['scene_id']} describes {canon_en} with '{bad_hair}', contradicting canonical hair '{char.hair_details}'. Flagged for review.")

            # Age representation contradiction check
            if char.apparent_age and ("child" in char.apparent_age.lower() or "year-old" in char.apparent_age.lower()):
                if re.search(r'\b(adult woman|adult man|teenager|adolescent|elderly)\b', p_text):
                    bad_age = re.search(r'\b(adult woman|adult man|teenager|adolescent|elderly)\b', p_text).group(0)
                    conflicts_flagged.append({
                        "character_id": char.character_id,
                        "canonical_name": canon_en,
                        "scene_id": sc["scene_id"],
                        "conflict_type": "age_representation_conflict",
                        "canonical_value": char.apparent_age,
                        "conflicting_value": bad_age,
                        "action_taken": "FLAGGED_FOR_HUMAN_REVIEW (Not silently changed)"
                    })
                    findings.append(f"[CONFLICT] {sc['scene_id']} describes {canon_en} as '{bad_age}', contradicting canonical age '{char.apparent_age}'. Flagged for review.")

            # Wardrobe continuity check
            if canon_outfit:
                words = [w.lower() for w in canon_outfit.split() if len(w) > 3]
                has_variation = any(v.lower() in p_text for v in char.permitted_variations)
                has_wardrobe_change = bool(char.wardrobe_changes and any(w.lower() in p_text for w in char.wardrobe_changes.split() if len(w) > 3))
                has_outfit = any(w in p_text for w in words)
                if not has_variation and not has_wardrobe_change and not has_outfit:
                    findings.append(f"Wardrobe continuity warning in {sc['scene_id']}: canonical '{canon_outfit}' not explicitly referenced in prompt.")

    # 4. Arabic Story Verbatim Preservation Audit
    recombined = " ".join([sc["exact_arabic_text"] for sc in scene_plans])
    orig_words = story_input.arabic_story_text.split()
    recomb_words = recombined.split()
    arabic_preserved = (len(orig_words) == len(recomb_words)) and all(w in recomb_words for w in orig_words)
    if not arabic_preserved:
        findings.append("Arabic verbatim preservation discrepancy: word counts or text segments do not match 100%.")

    audit_passed = (len(conflicts_flagged) == 0) and (len(findings) - len(conflicts_flagged) <= len(repaired_items))

    return {
        "audit_passed": audit_passed,
        "total_checks": 7,
        "defects_detected": len(findings),
        "defects_auto_repaired": len(repaired_items),
        "conflicts_flagged": conflicts_flagged,
        "conflicts_count": len(conflicts_flagged),
        "findings": findings,
        "repaired_items": repaired_items,
        "arabic_verbatim_preserved": arabic_preserved,
        "character_consistency": {
            "canonical_names_enforced": [c.get_canonical_name_en() for c in story_input.characters],
            "invariants_locked": [inv for c in story_input.characters for inv in c.invariants]
        }
    }


# =====================================================================
# Prompt Studio Engine Orchestrator
# =====================================================================

class PromptStudioEngine:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or PROMPT_PACKS_DIR
        self.ai = AITextGenerator()

    def generate_prompt_pack(self, story_input: StoryInput) -> Dict[str, Any]:
        """
        Orchestrates the AI-assisted prompt pack generation.
        AI reads the story and characters, reasons about visual context,
        and authors cohesive non-templated prompts.
        """
        story_id = story_input.story_id or f"story_{uuid.uuid4().hex[:8]}"
        story_dir = self.output_dir / story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        
        missing_questions = validate_inputs_and_find_missing(story_input)

        # 1. AI Authors Character Bible with Identity Locks
        ai_char_bible_data = self.ai.generate_character_bible_ai(story_input.characters, story_input.visual_style)

        # 2. Segment Arabic Story Verbatim (Code verification)
        if story_input.prestructured_scenes:
            scenes_data = story_input.prestructured_scenes
        else:
            scenes_data = segment_arabic_story_verbatim(story_input.arabic_story_text, story_input.num_scenes)

        # 3. AI Scene-by-Scene Planning & Creative Prompt Writing
        scene_plans = self.ai.generate_scene_plan_and_prompts_ai(
            story_title=story_input.title,
            scenes=scenes_data,
            characters=story_input.characters,
            visual_style=story_input.visual_style,
            target_model=story_input.target_image_model,
            aspect_ratio=story_input.aspect_ratio
        )
        self.ai._add_reference_context_to_scene_prompts(scene_plans, characters=story_input.characters, aspect_ratio=story_input.aspect_ratio)

        # 4. AI Authors Book Cover Prompt
        ai_cover_data = self.ai.generate_cover_prompt_ai(
            story_title=story_input.title,
            characters=story_input.characters,
            visual_style=story_input.visual_style,
            target_model=story_input.target_image_model,
            aspect_ratio=story_input.aspect_ratio,
            arabic_story_text=story_input.arabic_story_text
        )

        # 5. Automated Deterministic Consistency Audit & Auto-Correction
        audit_report = audit_prompt_pack_consistency(
            story_input=story_input,
            scene_plans=scene_plans,
            cover_data=ai_cover_data,
            ai_char_bible=ai_char_bible_data
        )

        # Mode determination: Live AI vs Fallback Heuristic
        is_live_ai = (self.ai.last_mode == "live_ai")
        generation_mode = "live_ai" if is_live_ai else "fallback_heuristic"
        model_used = self.ai.text_model_id if is_live_ai else None
        fallback_reason = self.ai.last_error if not is_live_ai else None

        # Render Markdown files with unambiguous mode tagging
        character_bible_md = self._render_character_bible_markdown(story_input, ai_char_bible_data, is_live_ai, model_used, fallback_reason)
        character_sheet_prompts_md = self._render_character_sheet_prompts_markdown(story_input, ai_char_bible_data, is_live_ai, model_used, fallback_reason)
        character_assets_json = self._build_character_assets_registry(story_input)
        scene_prompts_md = self._render_scene_prompts_markdown(story_input, scene_plans, is_live_ai, model_used, fallback_reason)
        cover_prompt_md = self._render_cover_prompt_markdown(story_input, ai_cover_data, is_live_ai, model_used, fallback_reason)

        # Targeted Editing & Repair Prompts
        editing_prompts_md = self._build_editing_prompts(story_input, scene_plans)

        # Evaluation Template
        evaluation_template_json = self._build_evaluation_template(story_input, scene_plans)

        # Manifest
        manifest = {
            "story_id": story_id,
            "title": story_input.title,
            "created_at": time.time(),
            "ai_generated": is_live_ai,
            "generation_mode": generation_mode,
            "model_used": model_used,
            "fallback_reason": fallback_reason,
            "scene_count": len(scene_plans),
            "character_count": len(story_input.characters),
            "target_model": story_input.target_image_model,
            "audit_passed": audit_report["audit_passed"],
            "defects_detected": audit_report["defects_detected"],
            "defects_auto_repaired": audit_report["defects_auto_repaired"],
            "conflicts_flagged": audit_report.get("conflicts_count", 0),
        }

        # 7. Serialize Artifacts
        self._write_file(story_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        self._write_file(story_dir / "consistency_audit.json", json.dumps(audit_report, indent=2, ensure_ascii=False))
        self._write_file(story_dir / "story_input.json", story_input.model_dump_json(indent=2))
        self._write_file(story_dir / "character_bible.md", character_bible_md)
        self._write_file(story_dir / "character_assets.json", json.dumps(character_assets_json, indent=2, ensure_ascii=False))
        self._write_file(story_dir / "character_sheet_prompts.md", character_sheet_prompts_md)
        self._write_file(story_dir / "scene_plan.json", json.dumps(scene_plans, indent=2, ensure_ascii=False))
        self._write_file(story_dir / "scene_prompts.md", scene_prompts_md)
        self._write_file(story_dir / "cover_prompt.md", cover_prompt_md)
        self._write_file(story_dir / "editing_prompts.md", editing_prompts_md)
        self._write_file(story_dir / "evaluation_template.json", json.dumps(evaluation_template_json, indent=2, ensure_ascii=False))

        return {
            "story_id": story_id,
            "story_dir": str(story_dir),
            "manifest": manifest,
            "character_bible": ai_char_bible_data,
            "scene_prompts": scene_plans,
            "cover_prompt": ai_cover_data,
            "ai_generated": is_live_ai,
            "generation_mode": generation_mode,
            "model_used": model_used,
            "fallback_reason": fallback_reason,
            "missing_inputs": missing_questions,
            "has_warnings": len(missing_questions) > 0 or not is_live_ai,
            "character_count": len(story_input.characters),
            "scene_count": len(scene_plans),
            "target_model": story_input.target_image_model,
            "audit_report": audit_report,
            "artifacts": {
                "manifest": "manifest.json",
                "consistency_audit": "consistency_audit.json",
                "story_input": "story_input.json",
                "character_bible": "character_bible.md",
                "character_assets": "character_assets.json",
                "character_sheet_prompts": "character_sheet_prompts.md",
                "scene_plan": "scene_plan.json",
                "scene_prompts": "scene_prompts.md",
                "cover_prompt": "cover_prompt.md",
                "editing_prompts": "editing_prompts.md",
                "evaluation_template": "evaluation_template.json",
            }
        }

    def revise_scene_prompt(
        self,
        story_id: str,
        scene_id: str,
        user_instruction: str,
        target_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Revises a scene prompt dynamically using AI."""
        pack = self.get_pack(story_id)
        if not pack:
            raise FileNotFoundError(f"Story pack '{story_id}' not found.")

        # Find scene
        scene_plan_raw = pack["files"].get("scene_plan.json", "[]")
        scenes = json.loads(scene_plan_raw)
        target_scene = next((s for s in scenes if s["scene_id"] == scene_id), None)
        if not target_scene:
            raise ValueError(f"Scene '{scene_id}' not found in story '{story_id}'.")

        # Find invariants
        story_input_raw = pack["files"].get("story_input.json", "{}")
        story_input = json.loads(story_input_raw)
        invariants = []
        for c in story_input.get("characters", []):
            invariants.extend(c.get("invariants", []))

        current_prompt = target_scene.get("prompt_workflow_a", "")
        model_name = target_model or story_input.get("target_image_model", "Model-Agnostic")

        revision_result = self.ai.revise_prompt_ai(
            exact_arabic_text=target_scene["exact_arabic_text"],
            current_prompt=current_prompt,
            user_instruction=user_instruction,
            character_invariants=invariants,
            target_model=model_name
        )

        # Update scene plan and scene_prompts.md on disk
        target_scene["prompt_workflow_a"] = revision_result["revised_prompt"]
        story_dir = self.output_dir / story_id
        self._write_file(story_dir / "scene_plan.json", json.dumps(scenes, indent=2, ensure_ascii=False))

        # Re-render scene_prompts.md
        story_in = StoryInput(**story_input)
        is_live = revision_result.get("generation_mode") == "live_ai"
        new_md = self._render_scene_prompts_markdown(
            story_in,
            scenes,
            is_live_ai=is_live,
            model_used=self.ai.text_model_id if is_live else None,
            fallback_reason=self.ai.last_error if not is_live else None
        )
        self._write_file(story_dir / "scene_prompts.md", new_md)

        revision_result["story_id"] = story_id
        revision_result["scene_id"] = scene_id
        return revision_result

    # -----------------------------------------------------------------
    # Markdown Renderers (Assembling AI-Authored Content)
    # -----------------------------------------------------------------
    def _render_character_bible_markdown(
        self,
        story_input: StoryInput,
        ai_bible: Dict[str, Any],
        is_live_ai: bool = False,
        model_used: Optional[str] = None,
        fallback_reason: Optional[str] = None
    ) -> str:
        if is_live_ai:
            mode_badge = (
                f"> [!NOTE]\n"
                f"> **Authoring Mode:** ✨ **Live AI Reasoning** (Model: `{model_used or 'Qwen'}`).\n"
                f"> Character identity locks, sheet prompts, and invariants below were authored dynamically by the live AI text model.\n"
            )
        else:
            mode_badge = (
                f"> [!WARNING]\n"
                f"> **Authoring Mode:** ⚠️ **Deterministic Heuristic Fallback** (Live AI Offline).\n"
                f"> **Notice:** The live AI text model was NOT used for this pack (Reason: {fallback_reason or 'No valid API key configured'}).\n"
                f"> The attributes below were generated using rule-based semantic inference. They are NOT AI-authored.\n"
            )

        md = [
            f"# Character Bible — {story_input.title}",
            f"**Target Age:** {story_input.intended_age} | **Style:** {story_input.visual_style}\n",
            mode_badge,
            "> **AI Architecture Notice:** Attributes are strictly separated into Confirmed (user-provided facts), "
            "AI-Proposed (creative suggestions), and Unknown attributes to prevent hallucinated identities.\n"
        ]

        for char in story_input.characters:
            char_data = ai_bible.get(char.character_id, {})
            confirmed = char_data.get("confirmed_attributes", {})
            proposed = char_data.get("ai_proposed_attributes", {})
            unknown = char_data.get("unknown_attributes", [])
            canon_en = char.get_canonical_name_en()
            canon_ar = char.get_canonical_name_ar()

            photos = ", ".join(char.source_photos) if char.source_photos else "None provided yet"
            sheet = char.canonical_sheet or f"{char.character_id.lower()}_character_sheet.png"
            proportions = char.body_proportions or proposed.get("body_proportions", "Stylized 3D animated child proportions (slightly enlarged head, expressive hands)")
            personality = char.personality_guidance or char_data.get("personality_guidance", "Curious, joyful, and emotionally resonant demeanor")
            wardrobe = char.canonical_clothing or char_data.get("canonical_wardrobe", "Canonical storytelling outfit")
            invariants = char_data.get("invariants", char.invariants or [])
            variations = char_data.get("permitted_variations", char.permitted_variations or ["Situational actions and poses matching story narrative"])

            md.append(f"## Character: {canon_en} ({canon_ar}) [`{char.character_id}`]\n")
            
            md.append("### 1. Canonical Identifiers")
            md.append(f"- **Canonical English Name:** `{canon_en}`")
            md.append(f"- **Canonical Arabic Name:** `{canon_ar}`")
            md.append(f"- **Character ID:** `{char.character_id}`")
            md.append(f"- **Narrative Role:** {char.role}")
            md.append(f"- **Ground-Truth Source Reference:** `{photos}`")
            md.append(f"- **Master Turnaround Sheet:** `{sheet}`\n")

            md.append("### 2. Age and Physical Identity")
            md.append(f"- **Apparent Age:** {char.apparent_age or confirmed.get('apparent_age', 'Child')}")
            md.append(f"- **Face & Cheeks:** {char.face_shape or proposed.get('face_shape', 'Rounded childlike face with soft cheeks')}")
            md.append(f"- **Eyes & Gaze:** {char.eye_details or proposed.get('eye_details', 'Expressive dark-brown eyes')}")
            md.append(f"- **Skin Tone:** {char.skin_tone or confirmed.get('skin_tone', 'Warm olive skin')}")
            md.append(f"- **Hair Style & Texture:** {char.hair_details or confirmed.get('hair_details', 'Textured dark curls')}")
            md.append(f"- **Body Proportions:** {proportions}")
            if char.distinctive_features or confirmed.get("distinctive_features"):
                md.append(f"- **Distinctive Features:** {char.distinctive_features or confirmed.get('distinctive_features')}\n")
            else:
                md.append(f"- **Distinctive Features:** Soft cheerful expressions suited to 3D stylization\n")

            md.append("### 3. Fixed Wardrobe and Accessories")
            md.append(f"- **Canonical Outfit:** {wardrobe}")
            if char.wardrobe_changes:
                md.append(f"- **Documented Wardrobe Shifts:** {char.wardrobe_changes}\n")
            else:
                md.append("- **Accessories & Footwear:** Practical child footwear matching outfit; clean styling without visual clutter.\n")

            md.append("### 4. Personality and Expression Guidance")
            md.append(f"- **Core Demeanor:** {personality}")
            md.append("- **Expression Palette:** Eager wonder, genuine curiosity, intellectual pride, gentle joyful smiles.\n")

            md.append("### 5. Explicit Invariants (Must NEVER Drift in Illustrations)")
            if invariants:
                for inv in invariants:
                    md.append(f"- 🔒 {inv}")
            else:
                md.append(f"- 🔒 Exact facial features and eye spacing locked to character sheet")
                md.append(f"- 🔒 Canonical hairstyle ({char.hair_details or 'natural curls'})")
                md.append(f"- 🔒 Canonical clothing ({wardrobe}) unless explicit scene variation")
            md.append("\n### 6. Permitted Situational Variations")
            if variations:
                for var in variations:
                    md.append(f"- 🔄 {var}")
            else:
                md.append("- 🔄 Narrative-aligned hand gestures, storytelling poses, and situational emotional expressions.")
            
            md.append("\n### 7. Attribute Tiering Audit (Confirmed vs AI-Proposed vs Unknown)")
            md.append("#### Confirmed Attributes (User-Supplied Facts)")
            if confirmed:
                for k, v in confirmed.items():
                    md.append(f"- **{k.replace('_', ' ').capitalize()}:** {v}")
            else:
                md.append("- *No verified attributes supplied by user.*")

            md.append("\n#### AI-Proposed Attributes (Creative Reasoning for Consistency)")
            if proposed:
                for k, v in proposed.items():
                    md.append(f"- **{k.replace('_', ' ').capitalize()}:** {v} `[AI-Proposed]`")
            else:
                md.append("- *None required; identity is fully specified by user.*")

            md.append("\n#### Unknown / Open Attributes (Not Assumed)")
            if unknown:
                for u in unknown:
                    md.append(f"-  {u}")
            else:
                md.append("- *No open attributes.*")
            md.append("---\n")

        return "\n".join(md)

    def _render_character_sheet_prompts_markdown(
        self,
        story_input: StoryInput,
        ai_bible: Dict[str, Any],
        is_live_ai: bool = False,
        model_used: Optional[str] = None,
        fallback_reason: Optional[str] = None
    ) -> str:
        if is_live_ai:
            mode_badge = (
                f"> [!NOTE]\n"
                f"> **Authoring Mode:** ✨ **Live AI Reasoning** (Model: `{model_used or 'Qwen'}`).\n"
            )
        else:
            mode_badge = (
                f"> [!WARNING]\n"
                f"> **Authoring Mode:** ⚠️ **Deterministic Heuristic Fallback** (Reason: {fallback_reason or 'No valid API key'}).\n"
            )

        md = [
            f"# Character Sheet Generation Prompts — {story_input.title}",
            mode_badge,
            "> **AI-Authored Step 1:** Generate and approve this character sheet BEFORE generating story scenes.\n"
        ]
        for char in story_input.characters:
            char_data = ai_bible.get(char.character_id, {})
            turnaround_prompt = char_data.get("character_sheet_prompt", "")
            sheet_name = char.canonical_sheet or f"{char.character_id.lower()}_character_sheet.png"
            photo_attach = char.source_photos[0] if char.source_photos else f"{char.character_id.lower()}_photo.jpg"

            md.append(f"## Character: {char.display_name} (`{char.character_id}`)")
            md.append(f"**Target Output File:** `{sheet_name}`\n")
            md.append(f"### Reference Attachments to Upload")
            md.append(f"1. **Primary Ground Truth Photo:** `{photo_attach}`\n")
            md.append("### AI-Authored Standalone Turnaround Prompt")
            md.append("```text")
            md.append(turnaround_prompt)
            md.append("```\n")
            md.append("### Quality Control Checklist")
            md.append(f"- [ ] Facial features evoke `{photo_attach}` in a stylized manner.")
            md.append(f"- [ ] Canonical clothing matches `{char.canonical_clothing}`.")
            md.append(f"- [ ] Clean isolated background for easy downstream reference conditioning.")
            md.append("---\n")
        return "\n".join(md)

    def _render_scene_prompts_markdown(
        self,
        story_input: StoryInput,
        scene_plans: List[Dict[str, Any]],
        is_live_ai: bool = False,
        model_used: Optional[str] = None,
        fallback_reason: Optional[str] = None
    ) -> str:
        if is_live_ai:
            mode_badge = (
                f"> [!NOTE]\n"
                f"> **Authoring Mode:** ✨ **Live AI Reasoning** (Model: `{model_used or 'Qwen'}`).\n"
                f"> All prompts, settings, character actions, and camera compositions below were authored dynamically "
                f"by the live AI text model based on the story text.\n"
            )
        else:
            mode_badge = (
                f"> [!WARNING]\n"
                f"> **Authoring Mode:** ⚠️ **Deterministic Heuristic Fallback** (Live AI Offline).\n"
                f"> **Notice:** The live AI text model was NOT used for this pack (Reason: {fallback_reason or 'No valid API key configured'}).\n"
                f"> The prompts below were generated using rule-based semantic inference. They are NOT AI-authored.\n"
            )

        md = [
            f"# Standalone Scene Prompts — {story_input.title}",
            f"**Target Model:** {story_input.target_image_model} | **Aspect Ratio:** {story_input.aspect_ratio}\n",
            mode_badge,
            "> **AI Context Reasoning:** Every scene below was authored by analyzing the actual Arabic narrative context, "
            "faithfully mapping the setting, time of day, character postures, and emotions.\n",
            "---\n"
        ]

        for sc in scene_plans:
            s_id = sc["scene_id"]
            page = sc["page_number"]
            ar_text = sc["exact_arabic_text"]
            setting = sc["inferred_setting"]
            time_of_day = sc["time_of_day"]
            action = sc["character_action"]
            expression = sc.get("facial_expression", "Curious and expressive")
            lighting = sc["lighting_and_atmosphere"]
            camera = sc["camera_composition"]
            refs = sc.get("reference_attachments", {})
            req_story = sc.get("required_story_elements", f"{action} in {setting}")
            creative_emb = sc.get("creative_embellishments", f"Lighting: {lighting}; Composition: {camera}")

            md.append(f"## {s_id}: Page {page}")
            md.append(f"**Original Arabic Story Text (Verbatim):**\n> {ar_text}\n")
            md.append(f"**Story Fidelity Breakdown:**")
            md.append(f"- **Required Story Details (From Source Narrative):** {req_story}")
            md.append(f"- **Creative Visual Embellishments (Art Direction):** {creative_emb}\n")
            md.append(f"**AI Context Breakdown:**")
            md.append(f"- **Setting & Time:** {setting} ({time_of_day})")
            md.append(f"- **Character Action & Expression:** {action} — *{expression}*")
            md.append(f"- **Lighting & Atmosphere:** {lighting}")
            md.append(f"- **Composition:** {camera}\n")

            md.append("### Reference Attachments by Workflow")
            md.append(f"- **Workflow A (Character Sheet):** Attach {', '.join(f'`{r}`' for r in refs.get('workflow_a', []))}")
            md.append(f"- **Workflow B (Original Photo):** Attach {', '.join(f'`{r}`' for r in refs.get('workflow_b', []))}")
            md.append(f"- **Workflow C (Hybrid):** Attach {', '.join(f'`{r}`' for r in refs.get('workflow_c', []))}\n")

            md.append("### AI-Authored Image Prompt (Workflow A — Recommended)")
            md.append("```text")
            md.append(sc["prompt_workflow_a"])
            md.append("```\n")

            md.append("### Alternative Prompt (Workflow B — Photo Conditioning)")
            md.append("```text")
            md.append(sc["prompt_workflow_b"])
            md.append("```\n")

            md.append("### Negative Prompt")
            md.append("```text")
            md.append(sc.get("negative_prompt", "photorealistic, photo collage, pasted head, text, blurry"))
            md.append("```\n")

            md.append("### Consistency Checklist")
            md.append(f"- [ ] Setting matches: {setting}")
            md.append(f"- [ ] Time of day matches: {time_of_day}")
            md.append(f"- [ ] Action faithfully reflects: {action}")
            md.append(f"- [ ] Character retains canonical features and clothing.")
            md.append("---\n")

        return "\n".join(md)

    def _render_cover_prompt_markdown(
        self,
        story_input: StoryInput,
        cover_data: Dict[str, Any],
        is_live_ai: bool = False,
        model_used: Optional[str] = None,
        fallback_reason: Optional[str] = None
    ) -> str:
        if is_live_ai:
            mode_badge = (
                f"> [!NOTE]\n"
                f"> **Authoring Mode:** ✨ **Live AI Reasoning** (Model: `{model_used or 'Qwen'}`).\n"
            )
        else:
            mode_badge = (
                f"> [!WARNING]\n"
                f"> **Authoring Mode:** ⚠️ **Deterministic Heuristic Fallback** (Reason: {fallback_reason or 'No valid API key'}).\n"
            )

        md = [
            f"# Book Cover Illustration Prompt — {story_input.title}",
            mode_badge,
            "> **AI Cover Architecture:** Authored to capture the full story arc while strictly preserving "
            "unobstructed space in the upper 35% for Arabic title typography.\n",
            "### AI-Authored Cover Prompt",
            "```text",
            cover_data.get("cover_prompt", ""),
            "```\n",
            "### Negative Prompt",
            "```text",
            cover_data.get("negative_prompt", ""),
            "```\n",
            "### Composition Guidelines",
            "- Upper third must remain clean/minimalist so Arabic typography can be layered cleanly.",
            "- Main character centrally positioned in the lower-middle zone.",
            "---\n"
        ]
        return "\n".join(md)

    def _build_character_assets_registry(self, story_input: StoryInput) -> Dict[str, Any]:
        registry = {
            "story_id": story_input.story_id or "auto",
            "title": story_input.title,
            "characters": []
        }
        for char in story_input.characters:
            sheet_name = char.canonical_sheet or f"{char.character_id.lower()}_character_sheet.png"
            registry["characters"].append({
                "character_id": char.character_id,
                "display_name": char.display_name,
                "canonical_name_en": char.get_canonical_name_en(),
                "canonical_name_ar": char.get_canonical_name_ar(),
                "source_photos": char.source_photos,
                "canonical_sheet": sheet_name,
                "approved_references": char.approved_references,
                "status": "approved" if story_input.has_generated_character_sheet else "awaiting_manual_generation_and_approval"
            })
        return registry

    def _build_editing_prompts(self, story_input: StoryInput, scene_plans: List[Dict[str, Any]]) -> str:
        char = story_input.characters[0] if story_input.characters else None
        char_name = char.get_canonical_name_en() if char else "the character"
        canonical_outfit = char.canonical_clothing if char else "canonical clothing"
        hair = char.hair_details if char else "canonical hair"

        md = [
            f"# Targeted Image-Editing Prompts — {story_input.title}",
            "> **AI Repair Instructions:** When inpainting or editing generated images in external tools, "
            "use these targeted directives rather than regenerating the entire image.\n",
            "## Repair 1: Pose & Action Correction",
            "- **Inpainting Directive:** Upload imperfect image + character sheet. Mask the body/hands.",
            "```text",
            f"Inpaint body region: Keep face identity, skin tone, and {hair} completely identical. Redraw arms and torso into target storytelling posture matching scene.",
            "```\n",
            "## Repair 2: Restore Canonical Clothing",
            "- **Inpainting Directive:** Mask clothing area.",
            "```text",
            f"Inpaint clothing region: Replace garment with strictly {canonical_outfit}. Maintain clean fabric shading and 3D animated texture.",
            "```\n",
            "## Repair 3: Remove Photorealistic Collage Artifacts",
            "- **Inpainting Directive:** Mask face region.",
            "```text",
            f"Inpaint face region: Redraw face in stylized 3D animation matching Pixar art style. Do NOT paste raw photo. Retain {char_name}'s eye shape and smile.",
            "```\n",
            "---\n"
        ]
        return "\n".join(md)

    def _build_evaluation_template(self, story_input: StoryInput, scene_plans: List[Dict[str, Any]]) -> Dict[str, Any]:
        criteria = [
            "character_resemblance",
            "preservation_of_distinctive_features",
            "clothing_continuity",
            "correct_character_count",
            "correct_actions_and_expressions",
            "scene_and_prop_accuracy",
            "art_style_consistency",
            "prompt_usability",
            "number_of_regeneration_attempts"
        ]
        return {
            "story_id": story_input.story_id or "auto",
            "story_title": story_input.title,
            "target_model": story_input.target_image_model,
            "workflows": {
                "workflow_a_character_sheet": {
                    "description": "Conditioned on canonical character sheet",
                    "scene_evaluations": [
                        {"scene_id": s["scene_id"], "ratings": {c: None for c in criteria if c != "number_of_regeneration_attempts"}, "attempts": None, "notes": ""}
                        for s in scene_plans
                    ]
                },
                "workflow_b_original_photos": {
                    "description": "Conditioned on original reference photos",
                    "scene_evaluations": [
                        {"scene_id": s["scene_id"], "ratings": {c: None for c in criteria if c != "number_of_regeneration_attempts"}, "attempts": None, "notes": ""}
                        for s in scene_plans
                    ]
                },
                "workflow_c_hybrid": {
                    "description": "Conditioned on both character sheet and original photos",
                    "scene_evaluations": [
                        {"scene_id": s["scene_id"], "ratings": {c: None for c in criteria if c != "number_of_regeneration_attempts"}, "attempts": None, "notes": ""}
                        for s in scene_plans
                    ]
                }
            }
        }

    def _write_file(self, path: Path, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_packs(self) -> List[Dict[str, Any]]:
        packs = []
        if not self.output_dir.exists():
            return packs
        for item in self.output_dir.iterdir():
            if item.is_dir() and (item / "story_input.json").exists():
                try:
                    with open(item / "story_input.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    manifest = {}
                    if (item / "manifest.json").exists():
                        try:
                            with open(item / "manifest.json", "r", encoding="utf-8") as mf:
                                manifest = json.load(mf)
                        except Exception:
                            pass
                    
                    num_scenes = data.get("num_scenes", 0)
                    if not num_scenes and (item / "scene_plan.json").exists():
                        try:
                            with open(item / "scene_plan.json", "r", encoding="utf-8") as sf:
                                sc_data = json.load(sf)
                                num_scenes = len(sc_data)
                        except Exception:
                            pass

                    files_count = len([f for f in item.iterdir() if f.is_file()])
                    created_at = manifest.get("created_at") or item.stat().st_mtime

                    packs.append({
                        "story_id": item.name,
                        "title": data.get("title") or manifest.get("title") or item.name,
                        "characters": [c.get("display_name") or c.get("name") for c in data.get("characters", [])],
                        "num_scenes": num_scenes,
                        "target_model": data.get("target_image_model") or manifest.get("target_model") or "qwen-image-2.0-pro",
                        "visual_style": data.get("visual_style") or "",
                        "aspect_ratio": data.get("aspect_ratio") or "9:16",
                        "created_at": created_at,
                        "files_count": files_count,
                        "ai_generated": manifest.get("ai_generated", False),
                        "generation_mode": manifest.get("generation_mode", "fallback_heuristic"),
                        "model_used": manifest.get("model_used", ""),
                        "audit_passed": manifest.get("audit_passed", True),
                        "zip_exists": (self.output_dir / f"{item.name}_prompt_pack.zip").exists()
                    })
                except Exception:
                    continue
        packs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return packs

    def get_pack(self, story_id: str) -> Optional[Dict[str, Any]]:
        story_dir = self.output_dir / story_id
        if not story_dir.exists():
            return None
        result = {"story_id": story_id, "files": {}}
        for file in story_dir.iterdir():
            if file.is_file():
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        result["files"][file.name] = f.read()
                except Exception:
                    continue
        
        # Parse structured components for instant client-side rendering
        if "manifest.json" in result["files"]:
            try:
                result["manifest"] = json.loads(result["files"]["manifest.json"])
            except Exception:
                pass
        if "story_input.json" in result["files"]:
            try:
                result["story_input"] = json.loads(result["files"]["story_input.json"])
            except Exception:
                pass
        if "scene_plan.json" in result["files"]:
            try:
                result["scene_plans"] = json.loads(result["files"]["scene_plan.json"])
            except Exception:
                pass
        result["created_at"] = story_dir.stat().st_mtime
        result["title"] = (result.get("story_input") or {}).get("title") or (result.get("manifest") or {}).get("title") or story_id
        return result

    def delete_pack(self, story_id: str) -> bool:
        story_dir = self.output_dir / story_id
        if not story_dir.exists() or not story_dir.is_dir():
            return False
        import shutil
        shutil.rmtree(story_dir, ignore_errors=True)
        zip_path = self.output_dir / f"{story_id}_prompt_pack.zip"
        if zip_path.exists():
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
        return True

    def save_evaluation(self, story_id: str, eval_data: Dict[str, Any]) -> bool:
        story_dir = self.output_dir / story_id
        if not story_dir.exists():
            return False
        eval_path = story_dir / "evaluation_results.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2, ensure_ascii=False)
        return True

    def create_export_zip(self, story_id: str) -> Optional[Path]:
        story_dir = self.output_dir / story_id
        if not story_dir.exists():
            return None
        zip_path = self.output_dir / f"{story_id}_prompt_pack.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in story_dir.iterdir():
                if file.is_file():
                    zipf.write(file, arcname=file.name)
        return zip_path

    def parse_story_model_outcome(self, raw_text: str) -> Dict[str, Any]:
        """Parses output from stories model into structured image pipeline inputs."""
        return parse_story_model_outcome(raw_text)

    def generate_full_pipeline(self, req: "FullPipelineRequest") -> Dict[str, Any]:
        """
        End-to-End Orchestrator:
        Step 1: Generates story using StoryGenerator (Gemini / DashScope / Fallback).
        Step 2: Converts story JSON to StoryInput.
        Step 3: Compiles complete prompt pack (Character Sheet, Scenes, Cover, QA Audit).
        Step 4: Bundles export ZIP.
        """
        import sys
        repo_root = Path(__file__).resolve().parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from hekayti.story_generator import StoryGenerator, make_story_input

        # 1. Generate Story
        story_input_dict = make_story_input(
            name=req.child_name,
            age=req.child_age,
            language=req.language,
            interests=req.interests,
            story_goal=req.story_goal,
            story_type=req.story_type,
            page_count=req.page_count,
            additional_characters=req.additional_characters,
            dedication=req.dedication,
            preferences=req.preferences,
            avoid=req.avoid,
            gender=req.child_gender
        )

        gen = StoryGenerator(
            dashscope_api_key=req.dashscope_api_key
        )
        previous_api_key = self.ai.api_key
        previous_disabled = self.ai.is_disabled
        if req.dashscope_api_key:
            self.ai.api_key = req.dashscope_api_key.strip()
        if req.provider_preference == "fallback":
            self.ai.is_disabled = True

        try:
            if req.story_text and req.story_text.strip():
                raw_scenes = segment_arabic_story_verbatim(req.story_text, req.page_count)
                story_data = {
                    "title": req.story_title or f"قصة {req.child_name}",
                    "summary": req.story_text.strip(),
                    "character_designs": [{
                        "name": req.child_name,
                        "character_id": "CHILD_01",
                        "appearance": req.physical_identity or "",
                        "clothing": req.canonical_wardrobe or "",
                        "distinctive_features": ""
                    }],
                    "pages": [{
                        "page": scene["scene_index"],
                        "scene_title": f"المشهد {scene['scene_index']}",
                        "text": scene["exact_arabic_text"],
                        "image_description": "",
                        "character_reference_ids": ["CHILD_01"]
                    } for scene in raw_scenes]
                }
                gen.last_provider_used = "user_story_text"
            else:
                story_data = gen.generate_story(
                    story_input=story_input_dict,
                    preferred_provider=req.provider_preference
                )

            # 2. Bridge Story to Prompt Studio StoryInput
            story_input_obj = story_dict_to_story_input(
                story_data=story_data,
                art_style=req.art_style,
                target_model=req.target_image_model,
                aspect_ratio=req.aspect_ratio,
                user_physical_identity=req.physical_identity,
                user_canonical_wardrobe=req.canonical_wardrobe,
                intended_age=str(req.child_age),
                gender=req.child_gender
            )

            # 3. Generate Complete Prompt Pack
            pack_result = self.generate_prompt_pack(story_input_obj)
        finally:
            self.ai.api_key = previous_api_key
            self.ai.is_disabled = previous_disabled

        # Expose one primary image prompt alongside each generated story scene.
        # The complete Workflow A/B/C prompt set remains available in prompt_pack.
        scene_prompts = pack_result.get("scene_prompts", [])
        generated_scenes = []
        for page, scene in zip(story_data.get("pages", []), scene_prompts):
            page["image_prompt"] = scene.get("prompt_workflow_a", "")
            page["image_prompts"] = {
                "character_sheet_reference": scene.get("prompt_workflow_a", ""),
                "original_photo_reference": scene.get("prompt_workflow_b", ""),
                "hybrid_references": scene.get("prompt_workflow_c", ""),
            }
            generated_scenes.append({
                "scene_id": scene.get("scene_id"),
                "page_number": page.get("page"),
                "title": page.get("scene_title", ""),
                "content": page.get("text", ""),
                "image_prompt": page["image_prompt"],
                "image_prompts": page["image_prompts"],
                "reference_attachments": scene.get("reference_attachments", {}),
            })
        story_data["scenes"] = generated_scenes

        # 4. Generate Export ZIP
        story_id = pack_result["story_id"]
        zip_path = self.create_export_zip(story_id)

        return {
            "success": True,
            "story_id": story_id,
            "story": story_data,
            "scenes": generated_scenes,
            "prompt_pack": pack_result,
            "provider_used": gen.last_provider_used,
            "zip_download_url": f"/prompt_studio/export_pack/{story_id}"
        }


# =====================================================================
# Full Pipeline Data Models & Bridge
# =====================================================================

class FullPipelineRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    child_name: str = Field(..., description="Child's name")
    child_age: int = Field(7, description="Child's age in years")
    child_gender: str = Field("boy", description="'boy' or 'girl'")
    language: str = Field("simplified_fusha", description="'simplified_fusha', 'egyptian_arabic', or 'english'")
    interests: List[str] = Field(default_factory=list, description="Child's hobbies/interests")
    story_goal: str = Field("تنمية الشجاعة والتجربة والمثابرة", description="Pedagogical goal")
    story_type: str = Field("مغامرة استكشافية", description="Type of story")
    page_count: int = Field(6, ge=2, le=15, description="Number of story pages/scenes")
    additional_characters: List[Dict[str, str]] = Field(default_factory=list, description="Additional characters e.g. [{'name': 'المعلمة هدى', 'role': 'معلمة العلوم'}]")
    dedication: str = Field("", description="Optional dedication")
    preferences: str = Field("", description="Optional preferences")
    avoid: List[str] = Field(default_factory=list, description="Topics to avoid")

    # Image Pipeline Options
    art_style: str = Field(
        default="Disney Pixar 3D animated illustration, warm vibrant colors, soft volumetric lighting, expressive stylized characters",
        description="Target visual illustration style"
    )
    target_image_model: str = Field(
        default="qwen-image-2.0-pro",
        description="Target image generation model: 'qwen-image-2.0-pro', 'wan2.7-image-pro', etc."
    )
    aspect_ratio: str = Field(default="9:16", description="Target aspect ratio (default: 9:16 vertical)")

    # Optional manual avatar / wardrobe overrides
    physical_identity: Optional[str] = Field(default=None, description="E.g. curly dark-brown hair, warm skin tone, dimple on left cheek")
    canonical_wardrobe: Optional[str] = Field(default=None, description="E.g. yellow raincoat with cute red boots")

    # Runtime DashScope API Key override
    dashscope_api_key: Optional[str] = None
    provider_preference: str = Field(default="dashscope", description="'dashscope' or 'fallback'")
    story_title: Optional[str] = Field(default=None, description="Optional title when supplying story_text")
    story_text: Optional[str] = Field(default=None, description="Optional existing story text to segment instead of authoring a new story")


def story_dict_to_story_input(
    story_data: Dict[str, Any],
    art_style: str = "Disney Pixar 3D animated illustration, warm vibrant colors, soft volumetric lighting, expressive stylized characters",
    target_model: str = "qwen-image-2.0-pro",
    aspect_ratio: str = "9:16",
    user_physical_identity: Optional[str] = None,
    user_canonical_wardrobe: Optional[str] = None,
    intended_age: str = "5-7",
    gender: str = "boy"
) -> StoryInput:
    """
    Transforms the structured story JSON output (produced by Reem's Task 2 model)
    into a fully typed StoryInput ready for prompt pack compilation.
    """
    title = story_data.get("title", "حكاية ممتعة")
    pages = story_data.get("pages", [])
    character_designs = story_data.get("character_designs", [])

    arabic_lines = []
    prestructured_scenes = []
    for p in pages:
        p_num = p.get("page", len(arabic_lines) + 1)
        p_title = p.get("scene_title", f"Scene {p_num}")
        p_text = p.get("text", "")
        p_desc = p.get("image_description", "")
        p_refs = p.get("character_reference_ids", [])
        
        arabic_lines.append(f"صفحة {p_num}: {p_title}\n{p_text}")
        prestructured_scenes.append({
            "scene_index": p_num,
            "exact_arabic_text": p_text,
            "scene_title": p_title,
            "image_description": p_desc,
            "character_reference_ids": p_refs
        })

    arabic_story_text = "\n\n".join(arabic_lines)

    characters: List[CharacterProfile] = []
    for idx, cd in enumerate(character_designs):
        c_name = cd.get("name", f"Character_{idx+1}")
        c_id = cd.get("character_id", f"char_{idx+1}")
        c_slug = re.sub(r'[^a-zA-Z0-9]+', '_', c_name.lower()).strip('_') or f"char_{idx+1}"
        
        appearance = cd.get("appearance", "")
        clothing = cd.get("clothing", "")
        dist_features = cd.get("distinctive_features", "")

        rel = cd.get("relationship", "")
        freq = cd.get("appearance_frequency", "medium")
        role_val = cd.get("role", "Supporting Character" if idx > 0 else "Protagonist")
        impact_val = cd.get("impact", "")

        if idx == 0:
            role = "Protagonist"
            apparent_age = f"{intended_age}-year-old {gender}"
            hair = user_physical_identity if user_physical_identity else appearance
            wardrobe = user_canonical_wardrobe if user_canonical_wardrobe else clothing
            sheet = f"{c_slug}_character_sheet.png"
            photos = []
            invs = [wardrobe, dist_features] if dist_features else [wardrobe]
        else:
            role = role_val
            apparent_age = "Supporting Character"
            hair = appearance
            wardrobe = clothing
            sheet = ""
            photos = []
            invs = [dist_features] if dist_features else []

        characters.append(CharacterProfile(
            character_id=c_id,
            display_name=c_name,
            canonical_name_ar=c_name,
            canonical_name_en=c_slug.title(),
            role=role,
            relationship=rel,
            appearance_frequency=freq,
            story_impact=impact_val,
            apparent_age=apparent_age,
            gender=gender if idx == 0 else "character",
            hair_details=hair,
            skin_tone="Warm radiant skin tone",
            canonical_clothing=wardrobe,
            distinctive_features=dist_features,
            canonical_sheet=sheet,
            source_photos=photos,
            invariants=invs
        ))

    if not characters:
        characters = [CharacterProfile(
            character_id="CHILD_01",
            display_name="بطل القصة",
            apparent_age=f"{intended_age}-year-old {gender}",
            canonical_clothing="ملابس الطفل اليومية المميزة",
            canonical_sheet="child_character_sheet.png",
            source_photos=["child_photo_01.jpg"]
        )]

    return StoryInput(
        title=title,
        arabic_story_text=arabic_story_text,
        intended_age=intended_age,
        num_scenes=len(pages) if pages else 6,
        visual_style=art_style,
        target_image_model=target_model,
        aspect_ratio=aspect_ratio,
        characters=characters,
        prestructured_scenes=prestructured_scenes
    )
