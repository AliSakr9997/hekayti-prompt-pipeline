"""Generate an example prompt pack for Karim's Space Journey."""
import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).resolve().parent / "image-deploy"))

from prompt_studio_engine import PromptStudioEngine, StoryInput, CharacterProfile

engine = PromptStudioEngine()

karim_story = (
    "كريم كان يحب النظر إلى السماء كل ليلة، يراقب النجوم اللامعة ويعدها بحماس شديد. "
    "في المدرسة، لاحظ المعلم شغف كريم الكبير بالفضاء، فأهداه كتاباً مليئاً بالصور الملونة لكوكب زحل وحلقاته البراقة. "
    "قرر كريم أن يصنع نموذجاً صغيراً للمجموعة الشمسية في غرفته باستخدام كرات ملونة وخيوط علقها في السقف. "
    "أعلنت المدرسة عن مسابقة للرسم بعنوان رحلة إلى الفضاء، فرسم كريم لوحة لصاروخ ينطلق نحو القمر وهو يقوده بابتسامة فخر. "
    "فاز كريم بالجائزة الأولى واحتفل مع والديه، مؤمناً بأن كل حلم عظيم يبدأ بخطوة شغف ومثابرة."
)

story_input = StoryInput(
    story_id="hekayti_karim_space_v1",
    title="رحلة كريم إلى الفضاء (Karim's Space Journey)",
    arabic_story_text=karim_story,
    intended_age="5-7",
    num_scenes=5,
    visual_style="Disney Pixar 3D animated illustration, warm vibrant colors, soft volumetric lighting, expressive stylized characters",
    aspect_ratio="1:1",
    output_format="High-resolution digital illustration, clean composition",
    educational_values="Curiosity, perseverance, passion for science, self-belief",
    target_image_model="Model-Agnostic / Universal (Midjourney, Flux, SDXL, Qwen)",
    workflow_preference="compare_all",
    has_generated_character_sheet=False,
    characters=[
        CharacterProfile(
            character_id="KARIM_01",
            display_name="كريم / Karim",
            role="Protagonist (Dreamer & Little Astronaut)",
            apparent_age="6-year-old boy",
            gender="boy",
            face_shape="round face with soft youthful cheeks",
            skin_tone="warm golden-olive skin",
            hair_details="short curly dark-brown hair, soft textured curls",
            eye_details="large expressive dark-brown eyes with a curious sparkle",
            body_proportions="Pixar-style child proportions, slightly oversized expressive head and animated hands",
            distinctive_features="small playful dimple on right cheek when smiling",
            canonical_clothing="royal navy blue hoodie with a small silver embroidered star on left chest, comfortable heather-grey joggers, clean white sneakers",
            wardrobe_changes="optional lightweight cardboard astronaut helmet in scene 3",
            source_photos=["karim_real_photo_01.jpg"],
            canonical_sheet="karim_character_sheet.png",
            invariants=[
                "eye color: warm dark brown",
                "hair: short curly dark-brown curls",
                "skin: warm golden-olive skin",
                "dimple: small dimple on right cheek",
                "clothing: navy blue hoodie with silver star patch"
            ]
        )
    ]
)

pack = engine.generate_prompt_pack(story_input)
print("SUCCESS: Generated prompt pack at:", pack["story_dir"])
print("Artifacts generated:", list(pack["artifacts"].keys()))
