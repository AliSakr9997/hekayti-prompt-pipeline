import os
import io
import base64
import time
import requests
import dashscope

from pathlib import Path
from PIL import Image

def _load_local_env():
    """Safely load .env file from project or app directory if present."""
    for base in [Path("."), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]:
        env_path = base / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

_load_local_env()

# ======================
# Initialize Qwen/DashScope clients
# ======================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
dashscope.api_key = DASHSCOPE_API_KEY

TEXT_MODEL_ID = os.getenv("TEXT_MODEL_ID", "qwen-plus")


def call_dashscope_chat(
    messages: list[dict],
    temperature: float = 0.5,
    model: str | None = None,
    api_key: str | None = None,
    max_retries: int = 3,
    timeout: int = 60
) -> str:
    """
    Public LLM chat completion gateway using Alibaba Cloud DashScope API.
    Supports both OpenAI-compatible format and DashScope native endpoints.
    Used by PromptStudioEngine to author creative prompts, character bibles,
    scene visual analyses, cover prompts, and prompt revisions.
    """
    effective_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
    if not effective_key or effective_key.startswith("mock_"):
        raise ValueError("DashScope API Key missing or unconfigured.")

    effective_model = model or os.getenv("TEXT_MODEL_ID", "qwen-plus")
    
    # Try international compatible endpoint first, fallback to domestic if needed
    endpoints = [
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    ]

    headers = {
        "Authorization": f"Bearer {effective_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": effective_model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    last_error = None
    for url in endpoints:
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        content = choices[0]["message"].get("content", "").strip()
                        if content:
                            return content
                    raise RuntimeError("DashScope returned empty text content.")

                detail = response.text[:400]
                is_rate_limited = response.status_code == 429 or "Throttling" in detail
                if is_rate_limited and attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    time.sleep(wait_time)
                    continue

                last_error = f"HTTP {response.status_code} from {url}: {detail}"
                # If authentication failed (401), trying another retry on the same endpoint won't help
                if response.status_code == 401:
                    break
            except Exception as ex:
                last_error = str(ex)
                if attempt < max_retries - 1:
                    time.sleep(2)

    raise RuntimeError(f"DashScope chat API failed: {last_error}")


def _extract_qwen_text(response):
    """Extract text content from DashScope response."""
    try:
        return response.output.choices[0].message.content
    except Exception:
        if isinstance(response, dict):
            return (
                response.get("output", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        return ""


def _generate_text_with_qwen(prompt, temperature=0.7, max_retries=5):
    """Generate text with Qwen text model using DashScope compatible API."""
    messages = [{"role": "user", "content": prompt}]
    return call_dashscope_chat(messages, temperature=temperature, max_retries=max_retries)

# ======================
# ======================
# Round-robin model rotation for rate limit optimization
# 2 models × 2 requests/minute = 4 images/minute
# ======================
_IMAGE_MODELS = [
    "qwen-image-2.0-pro-2026-04-22",  # 1st, 3rd, 5th... requests
    "qwen-image-2.0-pro-2026-06-22",  # 2nd, 4th, 6th... requests
]
_image_model_counter = 0

def _get_next_image_model():
    global _image_model_counter
    model = _IMAGE_MODELS[_image_model_counter % len(_IMAGE_MODELS)]
    _image_model_counter += 1
    print(f"[Model Rotation] Request #{_image_model_counter} → {model}")
    return model

# ======================
# Generate a scene image using Nano Banana
# ======================
def generate_scene_image(prompt, reference_image=None):
    """
    Generate an illustration using Alibaba Cloud Wan Image models.
    Supports reference image (child photo) for character consistency.
    Uses round-robin model rotation to maximize rate limits.
    """
    import os
    import dashscope
    from dashscope import MultiModalConversation
    import base64
    import io
    import requests
    from PIL import Image

    # Configure DashScope for Singapore region
    dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

    content_list = []

    if reference_image is not None:
        # reference_image is a PIL.Image, encode it to base64
        buffered = io.BytesIO()
        reference_image.save(buffered, format="PNG")
        encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')
        image_data = f"data:image/png;base64,{encoded_string}"
        
        # Add the image and strongly worded text to the content array
        content_list.append({"image": image_data})
        text_input = (
            "Use the provided image ONLY as a reference for the child's identity. "
            "Recreate the child as a fully illustrated character in a Pixar-style animated scene. "
            
            "CRITICAL INSTRUCTIONS: "
            "- DO NOT copy, paste, overlay, or embed the original photo. "
            "- DO NOT create a photorealistic image. "
            "- The output must be a fully stylized cartoon illustration. "
            "- Preserve the child's facial features, expression, and identity in a stylized way. "
            
            "STYLE REQUIREMENTS: "
            "- Disney Pixar-style 3D cartoon character "
            "- soft lighting, smooth shading, expressive eyes "
            "- child-friendly, colorful, warm atmosphere "
            
            "Generate this scene: "
            + prompt
        )
        content_list.append({"text": text_input})
    else:
        # Fallback if no reference image was provided
        content_list.append({"text": prompt})

    import time
    
    messages = [{"role": "user", "content": content_list}]

    # Pick the next model in the rotation
    selected_model = _get_next_image_model()

    max_retries = 5
    for attempt in range(max_retries):
        response = MultiModalConversation.call(
            model=selected_model,
            messages=messages,
            stream=False,
            n=1,
            watermark=False,
            prompt_extend=True,
            size="1024*1024",
        )

        if response.status_code == 200:
            # Extract the URL from the response content array
            image_url = None
            for content_item in response.output.choices[0].message.content:
                if "image" in content_item:
                    image_url = content_item["image"]
                    break
                    
            if not image_url:
                raise RuntimeError("API succeeded but returned no image URL.")
                
            # Download the image and convert to PIL so the rest of the application remains unchanged
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            return Image.open(io.BytesIO(img_response.content))
        else:
            if "Throttling" in getattr(response, 'code', '') or response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = 15 * (attempt + 1)
                    print(f"API Rate limit hit. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    err_msg = str(getattr(response, 'message', 'Unknown Error')).encode('ascii', 'replace').decode('ascii')
                    err_code = str(getattr(response, 'code', 'N/A')).encode('ascii', 'replace').decode('ascii')
                    raise RuntimeError(f"API Rate Limit Exhausted: {err_msg} (Code: {err_code})")
            else:
                err_msg = str(getattr(response, 'message', 'Unknown Error')).encode('ascii', 'replace').decode('ascii')
                err_code = str(getattr(response, 'code', 'N/A')).encode('ascii', 'replace').decode('ascii')
                raise RuntimeError(f"API Error: {err_msg} (Code: {err_code})")

# ======================
# Helper functions for story processing (using Qwen text model)
# ======================
def fetch_story_scenes_from_api(arabic_story_text, num_scenes=10):
    """
    Use Qwen to parse the Arabic story into EXACTLY `num_scenes` scenes with English image prompts.
    Uses the advanced few-shot prompt provided by the user.
    """
    import json

    prompt = f"""You are a story-to-image scene generator for children's Arabic stories.

## Task:
- **Input**: A full Arabic story.
- **Output**: A JSON object with exactly {num_scenes} scenes.

## Critical Instructions:
1. **Always produce exactly {num_scenes} scenes.**
   - Every scene must be **filled** (no empty "scene_text" or "image_prompt").
   - Each scene must be **roughly the same length** (balanced story split).
   - Do not make some scenes long and others short.
   - Each scene must range from 42 to 47 words 
   - If the story is short, expand descriptions naturally to reach {num_scenes} scenes.
   - If the story is long, compress and summarize evenly into {num_scenes} scenes.

2. Preserve the **meaning and tone** of the original Arabic story for each scene.
   - You may lightly split or merge phrasing to balance scenes.
   - Do not invent new characters, places, or events not present in the story.

3. For each scene, generate an **English image prompt** for an image generation model:
   - Start with: `animated illustration of ...`
   - Must be **under 70 tokens**.
   - Always include these keywords at the end:  
     `3D Pixar-style animated character, stylized proportions, smooth skin shading, cinematic lighting, high-quality digital illustration, vibrant pixar colorful child-friendly cartoon style, cheerful atmosphere, warm soft lighting, expressive facial features, detailed digital art`

4. **Verify before returning**:
   - Exactly {num_scenes} scenes exist.
   - All "scene_text" and "image_prompt" fields are filled.
   - Scene lengths are balanced and consistent.

5. **Do not** add extra explanations or formatting outside the JSON object.

## Return format (JSON):
Return the output as a valid JSON object with this exact structure for all {num_scenes} scenes:
{{
  "title": "<original Arabic title or first line>",
  "english_title": "<English translation of the title>",
  "scenes": [
    {{"scene_text": "Arabic text", "image_prompt": "English prompt"}},
    {{"scene_text": "Arabic text", "image_prompt": "English prompt"}}
  ]
}}

Here are few-shot examples of good vs. bad image prompts.  
Follow the **good examples** style and avoid the **bad examples** issues.

{{
  "good_examples": [
    {{
      "image_prompt": "animated cartoon illustration of a young boy sitting on a balcony at night, gazing at the starry sky and counting stars, imagining them as little lights guiding him to his dreams, pixar-style colorful cartoon, child-friendly comic style, cheerful atmosphere, warm soft lighting, expressive cartoon facial features, detailed digital cartoon art",
      "notes": "Good: Clear visual (boy + balcony + stars). Reinforced cartoon style."
    }},
    {{
      "image_prompt": "animated cartoon illustration of a boy and his father sitting on a rooftop at night, pointing at the moon while discussing how scientists study living in space, the boy smiling and dreaming of being part of that future, disney pixar cartoon style, colorful vibrant child-friendly illustration, cheerful atmosphere, glowing cartoon lighting, expressive cartoon facial features, 3D cartoon render look",
      "notes": "Good: Strong interaction, clear setting, heavy cartoon emphasis."
    }}
  ],
  "bad_examples": [
    {{
      "image_prompt": "animated illustration of a classroom where a teacher hands a colorful space book to a curious boy, filled with pictures of planets, especially Saturn with its shining rings, the boy's imagination soaring as he envisions flying around Saturn, realistic lighting, oil painting style",
      "notes": "Bad: Too many sub-scenes + includes non-cartoon keywords like realistic and oil painting."
    }}
  ],
  "guidelines": [
    "Always include cartoon-related keywords: 'animated cartoon illustration, pixar-style, disney cartoon, child-friendly comic style, colorful, cheerful, expressive cartoon faces'.",
    "Focus on one clear subject (the child) and one main action or setting.",
    "Avoid mixing imagination + reality in one prompt. Keep it grounded and simple.",
    "Do not use non-cartoon keywords like 'realistic', 'cinematic', 'oil painting', 'photorealistic'.",
    "End every prompt with cartoon style reinforcers."
  ]
}}

Arabic story:
{arabic_story_text}"""

    text = _generate_text_with_qwen(prompt, temperature=0.2, max_retries=5)

    # Strip markdown code fences if model wraps in ```json ... ```
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])   # remove opening ```
        text = text.rsplit("```", 1)[0].strip()   # remove closing ```

    json_data = json.loads(text)

    scenes_raw = json_data.get("scenes", [])
    if len(scenes_raw) > num_scenes:
        scenes_raw = scenes_raw[:num_scenes]
    elif len(scenes_raw) < num_scenes:
        fallback = scenes_raw[-1] if scenes_raw else {"scene_text": "", "image_prompt": "animated illustration of a child in a warm, colorful learning environment"}
        scenes_raw.extend([fallback] * (num_scenes - len(scenes_raw)))

    cover_title_ar = json_data.get("title", "قصتك السحرية")
    cover_title_en = json_data.get("english_title", json_data.get("English Title", "Magical Story"))
    first_scene_prompt = ""
    if scenes_raw:
        first_scene_prompt = scenes_raw[0].get("image_prompt") or ""

    # Build cover entry
    cover_data = {
        "page_number": 0,
        "scene_text": cover_title_ar,
        "scene_text_en": (
            f"animated illustration of a magical storybook cover titled '{cover_title_en}', "
            f"featuring the child hero and the main theme, vibrant child-friendly composition"
            if not first_scene_prompt
            else f"animated illustration of a magical storybook cover titled '{cover_title_en}', inspired by this scene: {first_scene_prompt}"
        )
    }

    # Build scene entries
    scenes_list = []
    for idx, item in enumerate(scenes_raw):
        # Handle dynamic keys like scene_1_text, or static scene_text
        s_text = item.get("scene_text") or item.get(f"scene_{idx+1}_text") or ""
        i_prompt = item.get("image_prompt") or item.get(f"image_{idx+1}_prompt") or ""
        
        scenes_list.append({
            "page_number": idx + 1,
            "scene_text": s_text,
            "scene_text_en": i_prompt
        })

    return [cover_data] + scenes_list

def build_prompt(child_name, image_prompt, child_gender):
    """Build the prompt for image generation using the extracted English prompt and adding negative prompts."""
    negative_prompt = (
        "text, words, letters, watermark, logo, captions, signature, typography, "
        "photorealistic, real photo, realistic skin, "
        "face overlay, pasted face, collage, cut and paste, photo insert, "
        "low quality, blurry, deformed face, bad anatomy, extra limbs, "
        "distorted eyes, ugly, poorly drawn"
    )
    
    return (
        f"{image_prompt}. "
        f"The main character is a young {child_gender} named {child_name}. "
        "The scene must be child-safe, joyful, and easy to understand visually. "
        "Recreate the child as a Pixar-style animated character based on the reference image. "
        "CRITICAL RULES: "
        "- DO NOT paste or overlay the original face. "
        "- DO NOT generate photorealistic output. "
        "- Fully redraw the child in cartoon style. "
        "- Preserve identity (face shape, hairstyle, age impression) but reinterpret it as animation. "
        "STYLE: Disney Pixar 3D animation, soft lighting, smooth shading, expressive eyes, colorful environment. "
        "NO TEXT, NO LETTERS, NO LOGOS, NO WATERMARK. "
        f"{negative_prompt}"
    )

# ======================
# Load initial image from URL or base64
# ======================
def load_init_image(image_url):
    """Download an image from a URL and return it as a PIL Image."""
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).resize((1024, 1024))

# ======================
# Text Generation: Arabic Story
# ======================
def generate_arabic_story(name, hobby, num_chapters=10, age="5"):
    """Generate an Arabic children's story using Qwen text model."""

    prompt = f"""You are a creative Arabic children's book author.
Write an engaging story EXCLUSIVELY in Arabic.
The main character is a {age} year old child named '{name}'. Their favorite hobby is '{hobby}'.

Strict Instructions:
1. The story MUST be written entirely in Arabic.
2. Start with a short title related to {hobby}.
3. The story MUST be divided into exactly {num_chapters} numbered chapters in this format: فصل 1:, فصل 2:, etc.
4. Each chapter should contain 3-4 short, clear sentences suitable for children.
5. Keep the full plot centered on {hobby} with logical progression.
6. Keep content child-safe: no violence, fear, or inappropriate themes.
7. End with a positive educational takeaway in Arabic."""

    return _generate_text_with_qwen(prompt, temperature=0.8, max_retries=5)

# ======================
# Generate Interactive Story Quiz
# ======================
def generate_story_quiz(story_text, age="5"):
    """
    Generate exactly 5 engaging, educational MCQs in Arabic based on the story.
    Adapted for the child's specific age group.
    Returns a list of dicts: {"question": str, "options": list[str], "correct_index": int}
    """
    import json
    import time
    
    prompt = f"""You are a fun and educational quiz generator for children.
I will give you an Arabic children's story.
You must generate exactly 5 Multiple Choice Questions (MCQs) in Arabic based on this story.
The questions must be perfectly tailored for a child who is {age} years old.
Make the questions engaging, fun, and ensure they extract a useful lesson, moral, or healthy habit from the story.
Do not ask trick questions.

OUTPUT FORMAT:
Return ONLY a strictly valid JSON array of 5 objects. Do not use markdown wrappers.
Each object must have:
- "question": The question text in Arabic.
- "options": An array of exactly 3 possible answer strings in Arabic.
- "correct_index": The integer index (0, 1, or 2) of the correct answer inside the options array.
All options must be short, clear, and distinct.

Story:
{story_text}
"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            raw = _generate_text_with_qwen(prompt, temperature=0.2, max_retries=3)
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            
            quiz_data = json.loads(raw.strip())
            
            # Validate format sanity
            valid = (
                isinstance(quiz_data, list)
                and len(quiz_data) == 5
                and all(
                    isinstance(item, dict)
                    and "question" in item
                    and "options" in item
                    and "correct_index" in item
                    and isinstance(item["options"], list)
                    and len(item["options"]) == 3
                    and isinstance(item["correct_index"], int)
                    and 0 <= item["correct_index"] <= 2
                    for item in quiz_data
                )
            )
            if valid:
                return quiz_data
            else:
                raise ValueError("JSON returned does not match the required 5-question MCQ format.")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise RuntimeError(f"Failed to generate story quiz: {str(e)}")

# ======================
# Text Diacritization (Tashkeel) using Qwen
# ======================
def diacritize_arabic(text):
    """
    Use Qwen to add diacritics (tashkeel) to the Arabic text based on meaning.
    """
    prompt = f"قم بتشكيل النص العربي التالي بالكامل تشكيلاً لغوياً دقيقاً، مع الحفاظ على نفس الكلمات تماماً وبدون أي إضافات أو شرح:\n\n{text}"
    try:
        result = _generate_text_with_qwen(prompt, temperature=0.2, max_retries=3)
        # Strip any accidental markdown or quotes from the model output
        result = result.strip().strip('"').strip("'")
        return result
    except Exception as e:
        print(f"Diacritization warning: {e}")
        return text # fallback to original text if fails

# ======================
# Audio Generation API using Edge-TTS
# ======================
import os

_xtts_model = None
_xtts_device = None

def _get_xtts_model():
    global _xtts_model, _xtts_device
    if _xtts_model is None:
        os.environ["COQUI_TOS_AGREED"] = "1"
        import torch
        from TTS.api import TTS
        print("Loading XTTS-v2 model on demand...")
        _xtts_device = "cuda" if torch.cuda.is_available() else "cpu"
        _xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(_xtts_device)
        print("XTTS-v2 loaded on", _xtts_device)
    return _xtts_model

def _split_sentences(text):
    import re
    return [s.strip() for s in re.split(r'[.،!?؟]', text) if s.strip()]

def generate_audio(text, chapter=1):
    """
    Diacritize the Arabic text and generate audio.
    Uses XTTS-v2 strictly.
    """
    from pydub import AudioSegment
    
    # 1. Diacritize Text
    diacritized_text = diacritize_arabic(text)
    
    # 2. Generate Audio
    wav_path = os.path.join(os.path.dirname(__file__), "voice_ref.wav")
    sentences = _split_sentences(diacritized_text)
    if not sentences:
        sentences = [diacritized_text]
        
    final_audio = AudioSegment.empty()
    
    for i, sentence in enumerate(sentences):
        temp_path = f"tmp_xtts_{i}.wav"
        (_get_xtts_model()).tts_to_file(
            text=sentence,
            speaker_wav=wav_path,
            language="ar",
            file_path=temp_path,
            split_sentences=False
        )
        audio = AudioSegment.from_wav(temp_path)
        final_audio += audio
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    out_path = "tmp_xtts_final.wav"
    final_audio.export(out_path, format="wav")
    
    with open(out_path, "rb") as f:
        audio_data = f.read()
    if os.path.exists(out_path):
        os.remove(out_path)
    return audio_data, "audio/wav"
