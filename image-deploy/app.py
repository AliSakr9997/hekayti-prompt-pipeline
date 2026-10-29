import io
import base64
import os
import json
import time
import uuid
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("===== Starting app.py imports =====")

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from PIL import Image
from hekayti.models import CharacterProfile as CoreCharacterProfile, CharacterSceneState, Scene, Strategy, Wardrobe
from hekayti.prompting import PromptCompiler

try:
    import demo.server as demo_server
    logger.info("===== demo.server imported successfully =====")
except Exception as e:
    logger.warning(f"Could not import demo.server: {e}")
    demo_server = None

logger.info("===== Importing model_utils & prompt_studio_engine =====")
try:
    from model_utils import (
        generate_scene_image,
        fetch_story_scenes_from_api,
        build_prompt,
        load_init_image,
        generate_arabic_story,
        generate_story_quiz,
        generate_audio,
    )
    from prompt_studio_engine import (
        PromptStudioEngine,
        StoryInput,
        CharacterProfile,
        EvaluationRating,
        PromptRevisionRequest,
        FullPipelineRequest,
        story_dict_to_story_input,
        validate_inputs_and_find_missing,
        parse_story_model_outcome
    )
    logger.info("===== Modules imported successfully =====")
except Exception as e:
    logger.error(f"===== FAILED to import modules: {e} =====")
    raise

# ======================
# Initialize FastAPI app
# ======================
app = FastAPI(title="Hekayti — Manual AI Illustration Prompt Studio", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
PROMPT_ONLY_MODE = True

prompt_studio_engine = PromptStudioEngine()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Setup Jinja2 templates
if TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
else:
    templates = Jinja2Templates(directory="templates")

# Mount a 'static' directory if it exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("Static files mounted from %s", STATIC_DIR)

# Mount experiment and generated asset directories from demo server
if demo_server:
    demo_server.GENERATED.mkdir(parents=True, exist_ok=True)
    demo_server.EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=str(demo_server.GENERATED)), name="generated")
    app.mount("/experiments", StaticFiles(directory=str(demo_server.EXPERIMENTS)), name="experiments")
    logger.info("Mounted /generated and /experiments from demo server paths")

@app.get("/")
def read_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Welcome to Hekayti Prompt Studio! Open static/index.html to use the studio."}

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Hekayti Prompt Studio", "version": "3.0"}

# ======================
# Experiment Lab & Benchmark API Endpoints (Merged from demo.server)
# ======================

@app.get("/api/status")
def api_status():
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server is not available")
    try:
        auth = demo_server.parse_json_output(demo_server.run_bailian(["auth", "status"]))
        return {"authenticated": bool(isinstance(auth, dict) and auth.get("authenticated"))}
    except Exception as error:
        return Response(content=json.dumps({"authenticated": False, "error": str(error)}), status_code=503, media_type="application/json")

@app.get("/api/experiments")
def api_experiments():
    if not demo_server:
        return {"runs": []}
    runs = []
    if demo_server.EXPERIMENTS.is_dir():
        for run_dir in sorted(demo_server.EXPERIMENTS.glob("run_*"), reverse=True):
            summary_path = run_dir / "summary.json"
            if summary_path.is_file():
                try:
                    run_data = json.loads(summary_path.read_text(encoding="utf-8"))
                    run_data["created_at"] = run_dir.stat().st_mtime
                    run_data["run_dir"] = run_dir.name
                    runs.append(run_data)
                except Exception:
                    pass
    return {"runs": runs}

@app.delete("/api/experiments/{run_id}")
def delete_experiment(run_id: str):
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo_server unavailable")
    run_dir = demo_server.EXPERIMENTS / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Experiment run '{run_id}' not found")
    import shutil
    shutil.rmtree(run_dir, ignore_errors=True)
    return {"success": True, "run_id": run_id}

@app.get("/api/quota")
def api_quota():
    if PROMPT_ONLY_MODE:
        return {"models": [], "disabled": True, "message": "Prompt-only mode is enabled; image quota is protected."}
    if not demo_server:
        return Response(content=json.dumps({"models": [], "error": "demo.server unavailable"}), status_code=503, media_type="application/json")
    try:
        raw = demo_server.parse_json_output(demo_server.run_bailian(["usage", "free"], timeout=60))
        values = raw if isinstance(raw, list) else []
        models = [
            {
                "model": item.get("model"),
                "remaining": item.get("remaining"),
                "total": item.get("total"),
                "usagePercent": item.get("usagePercent"),
                "expires": item.get("expires"),
            }
            for item in values
            if isinstance(item, dict)
            and item.get("model") in demo_server.IMAGE_MODELS
        ]
        return {"models": models}
    except Exception as error:
        return Response(content=json.dumps({"models": [], "error": str(error)}), status_code=503, media_type="application/json")

@app.post("/api/upload-photo")
async def api_upload_photo(request: Request):
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        filename, content = demo_server.extract_multipart(body, content_type)
        character_id = request.headers.get("x-character-id", "character-1")
        run_dir = demo_server.EXPERIMENTS / "current" / "characters" / character_id / "source_photos"
        run_dir.mkdir(parents=True, exist_ok=True)
        destination = run_dir / f"{uuid.uuid4().hex[:10]}-{filename}"
        destination.write_bytes(content)
        dimensions = demo_server.dimensions_for(destination)
        record = {
            "character_id": character_id,
            "path": str(destination.relative_to(demo_server.ROOT.parent)),
            "filename": filename,
            "bytes": len(content),
            "dimensions": dimensions,
        }
        demo_server.save_json(destination.with_suffix(".json"), record)
        return record
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.post("/api/profile")
async def api_profile(request: Request):
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        data = await request.json()
        result = demo_server.create_profile(data)
        return result
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error))

@app.post("/api/plan-story")
async def api_plan_story(request: Request):
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        data = await request.json()
        result = demo_server.plan_story(data)
        return result
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error))

@app.post("/api/experiment")
async def api_experiment(request: Request):
    if PROMPT_ONLY_MODE:
        raise HTTPException(status_code=403, detail="Prompt-only mode is enabled. Export prompts and test images manually.")
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        data = await request.json()
        result = demo_server.run_experiment(data)
        return result
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error))

@app.post("/api/evaluation")
async def api_evaluation(request: Request):
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        data = await request.json()
        run_id = str(data.get("run_id") or "")
        if not run_id or not isinstance(data.get("ratings"), list):
            raise ValueError("run_id and ratings are required")
        ratings = data["ratings"]
        by_arm: dict[str, list[float]] = {}
        for rating in ratings:
            if not isinstance(rating, dict) or rating.get("score") in (None, ""):
                continue
            score = float(rating["score"])
            if not 1 <= score <= 5:
                raise ValueError("rating scores must be between 1 and 5")
            by_arm.setdefault(str(rating.get("arm") or "unknown"), []).append(score)
        aggregates = {
            arm: {
                "average": round(sum(scores) / len(scores), 2),
                "answered": len(scores),
                "maximum": 5,
            }
            for arm, scores in by_arm.items()
        }
        ranked = sorted(
            aggregates.items(),
            key=lambda item: (item[1]["average"], item[1]["answered"]),
            reverse=True,
        )
        data["aggregates"] = aggregates
        data["recommendation"] = (
            {"arm": ranked[0][0], "average": ranked[0][1]["average"]}
            if ranked else None
        )
        evaluation_path = demo_server.EXPERIMENTS / run_id / "evaluation.json"
        demo_server.save_json(evaluation_path, data)
        return {
            "saved": str(evaluation_path.relative_to(demo_server.ROOT.parent)),
            "aggregates": aggregates,
            "recommendation": data["recommendation"],
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.post("/api/compile-prompt")
async def api_compile_prompt(request: Request):
    try:
        data = await request.json()
        wardrobe_data = data.get("wardrobe") if isinstance(data.get("wardrobe"), dict) else {}
        wardrobe = Wardrobe(
            top=str(wardrobe_data.get("top", "")), outerwear=str(wardrobe_data.get("outerwear", "")),
            bottom=str(wardrobe_data.get("bottom", "")), dress=str(wardrobe_data.get("dress", "")),
            shoes=str(wardrobe_data.get("shoes", "")),
            accessories=tuple(str(x) for x in wardrobe_data.get("accessories", []) if str(x).strip()),
            mode=str(wardrobe_data.get("mode", "preferred")),
        )
        character = CoreCharacterProfile.create(
            id="character-1", name=str(data.get("name") or "Child"), age=str(data.get("age") or "child"),
            appearance=tuple(str(x) for x in data.get("appearance", ["consistent facial features"])),
            wardrobe_config=wardrobe, negative_constraints=("extra characters", "text", "watermark", "identity drift"),
        )
        state = CharacterSceneState(
            character_id="character-1", action=str(data.get("action") or "standing naturally"),
            expression=str(data.get("expression") or "happy"),
            mandatory_costume=str(data.get("mandatory_costume")) if data.get("mandatory_costume") else None,
        )
        scene = Scene.create(
            id="scene-1", description=str(data.get("scene") or "A storybook scene"),
            setting=str(data.get("setting") or "a colorful setting"), character_ids=["character-1"],
            character_states=[state], reference_asset_ids=[str(x) for x in data.get("references", [])],
        )
        compiled = PromptCompiler(Strategy(str(data.get("strategy") or "hybrid"))).compile(scene, {"character-1": character})
        return {"prompt_only": True, "positive": compiled.positive, "negative": compiled.negative,
                "reference_ids": compiled.reference_ids, "strategy": compiled.strategy.value, "sections": compiled.sections}
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))

@app.post("/api/generate")
async def api_generate(request: Request):
    if PROMPT_ONLY_MODE:
        raise HTTPException(status_code=403, detail="Prompt-only mode is enabled; image-generation API calls are disabled.")
    if not demo_server:
        raise HTTPException(status_code=503, detail="demo.server unavailable")
    try:
        data = await request.json()
        result = demo_server.generate(data)
        return result
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error))

# ======================
# Legacy API Models (Kept for compatibility)
# ======================
class StoryTextRequest(BaseModel):
    name: str
    hobby: str
    num_chapters: int = 10
    age: str = "5"

class StoryRequest(BaseModel):
    arabic_story_text: str
    child_gender: str
    child_1st_name_arabic: str
    story_topic_arabic: str
    num_chapters: int = 10
    init_image_url: str | None = None
    init_image_base64: str

class ExtractScenesRequest(BaseModel):
    arabic_story_text: str
    num_scenes: int = 10

class SingleImageRequest(BaseModel):
    scene_text_en: str
    child_gender: str
    child_1st_name_arabic: str
    init_image_base64: str

class StoryQuizRequest(BaseModel):
    story_text: str
    age: str = "5"

class StoryPageModel(BaseModel):
    scene_text: str
    image_data: str

class RenderStoryRequest(BaseModel):
    final_poster_url: str | None = None
    scenes: list[StoryPageModel]

class AudioRequest(BaseModel):
    text: str
    chapter: int = 1

# ======================
# Prompt Studio Endpoints (Primary Product)
# ======================

@app.post("/prompt_studio/validate")
def validate_prompt_studio_input(request: StoryInput):
    """
    Checks for essential missing details rather than hallucinating them.
    Returns focused questions for the user if necessary.
    """
    questions = validate_inputs_and_find_missing(request)
    return {
        "valid": len(questions) == 0,
        "missing_questions": questions
    }

@app.post("/prompt_studio/create_pack")
def create_prompt_pack(request: StoryInput):
    """
    Generates an AI-assisted prompt pack with character bible, character sheet prompts,
    exact Arabic scene breakdown, AI-authored scene prompts for Workflows A, B, and C,
    cover prompt, targeted repair prompts, and evaluation template.
    Zero automated image generation calls are made.
    """
    try:
        pack = prompt_studio_engine.generate_prompt_pack(request)
        return pack
    except Exception as e:
        logger.error(f"Failed to generate prompt pack: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt pack generation failed: {str(e)}")

@app.post("/prompt_studio/generate_full_pipeline")
def generate_full_pipeline_endpoint(request: FullPipelineRequest):
    """
    Complete End-to-End Pipeline:
    Ingests user input (child details, story goal/interests, target image model)
    -> Generates children's story JSON via Gemini/DashScope/Fallback (Reem Task 2)
    -> Bridges character designs and page visual descriptions into Image Pipeline
    -> Generates complete Prompt Pack (Character Sheet, Scene Prompts, Cover Prompt, QA Audit)
    -> Packages downloadable ZIP.
    """
    try:
        result = prompt_studio_engine.generate_full_pipeline(request)
        return result
    except Exception as e:
        logger.error(f"Full pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Full pipeline failed: {str(e)}")

@app.post("/prompt_studio/generate_story_only")
def generate_story_only_endpoint(request: FullPipelineRequest):
    """
    Generates only the structured children's story JSON (Reem Task 2 format).
    """
    try:
        from hekayti.story_generator import StoryGenerator, make_story_input
        story_input_dict = make_story_input(
            name=request.child_name,
            age=request.child_age,
            language=request.language,
            interests=request.interests,
            story_goal=request.story_goal,
            story_type=request.story_type,
            page_count=request.page_count,
            additional_characters=request.additional_characters,
            dedication=request.dedication,
            preferences=request.preferences,
            avoid=request.avoid,
            gender=request.child_gender
        )
        gen = StoryGenerator(
            dashscope_api_key=request.dashscope_api_key
        )
        story_data = gen.generate_story(story_input_dict, preferred_provider=request.provider_preference)
        return {
            "success": True,
            "provider_used": gen.last_provider_used,
            "story": story_data
        }
    except Exception as e:
        logger.error(f"Story generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Story generation failed: {str(e)}")

class StoryOutcomeRequest(BaseModel):
    raw_text: str

@app.post("/prompt_studio/parse_story_outcome")
def parse_story_outcome_endpoint(request: StoryOutcomeRequest):
    """
    Parses outcomes from the Hekayti story model (make_input(...) plus story scenes)
    into structured inputs ready for the image prompt generation pipeline.
    """
    try:
        parsed = prompt_studio_engine.parse_story_model_outcome(request.raw_text)
        return parsed
    except Exception as e:
        logger.error(f"Story outcome parsing failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse story outcome: {str(e)}")

@app.post("/prompt_studio/revise_prompt")
def revise_prompt_endpoint(request: PromptRevisionRequest):
    """
    AI-driven prompt revision endpoint.
    Takes user natural language instruction, analyzes original Arabic scene context and invariants,
    and returns dynamically rewritten prompt.
    """
    try:
        result = prompt_studio_engine.revise_scene_prompt(
            story_id=request.story_id,
            scene_id=request.scene_id,
            user_instruction=request.user_instruction,
            target_model=request.target_model
        )
        return result
    except Exception as e:
        logger.error(f"Prompt revision failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt revision failed: {str(e)}")

@app.get("/prompt_studio/list_packs")
def list_prompt_packs():
    """Lists all saved prompt packs on disk."""
    return {"packs": prompt_studio_engine.list_packs()}

@app.get("/prompt_studio/pack/{story_id}")
def get_prompt_pack(story_id: str):
    """Retrieves all generated files and artifacts for a prompt pack."""
    pack = prompt_studio_engine.get_pack(story_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Prompt pack not found")
    return pack

@app.delete("/prompt_studio/pack/{story_id}")
def delete_prompt_pack(story_id: str):
    """Deletes a saved prompt pack and its export ZIP archive."""
    success = prompt_studio_engine.delete_pack(story_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Story pack '{story_id}' not found")
    return {"success": True, "story_id": story_id}

@app.post("/prompt_studio/save_evaluation")
def save_prompt_evaluation(eval_req: EvaluationRating):
    """Saves user manual ratings for Workflows A, B, and C."""
    pack = prompt_studio_engine.get_pack(eval_req.story_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Story not found")
    
    eval_raw = pack.get("files", {}).get("evaluation_template.json", "{}")
    try:
        eval_dict = json.loads(eval_raw)
    except Exception:
        eval_dict = {}
        
    wf_key = eval_req.workflow_id
    if wf_key in eval_dict.get("workflows", {}):
        scene_list = eval_dict["workflows"][wf_key].get("scene_evaluations", [])
        matched = False
        for sc in scene_list:
            if sc.get("scene_id") == eval_req.scene_id:
                sc["ratings"].update(eval_req.ratings)
                sc["attempts"] = eval_req.attempts
                sc["notes"] = eval_req.notes
                matched = True
                break
        if not matched:
            scene_list.append({
                "scene_id": eval_req.scene_id,
                "ratings": eval_req.ratings,
                "attempts": eval_req.attempts,
                "notes": eval_req.notes
            })
                
    success = prompt_studio_engine.save_evaluation(eval_req.story_id, eval_dict)
    return {"status": "saved" if success else "failed"}

@app.get("/prompt_studio/export_pack/{story_id}")
def export_prompt_pack(story_id: str):
    """Exports and downloads the complete prompt pack as a ZIP archive."""
    zip_path = prompt_studio_engine.create_export_zip(story_id)
    if not zip_path or not zip_path.exists():
        raise HTTPException(status_code=404, detail="Prompt pack could not be exported")
    return FileResponse(
        path=str(zip_path),
        filename=f"{story_id}_prompt_pack.zip",
        media_type="application/zip"
    )

# ======================
# Companion & Legacy Endpoints
# ======================

@app.post("/generate_story_text")
def generate_story_text(request: StoryTextRequest):
    """Generate Arabic children's story text using Qwen/DeepSeek text model."""
    try:
        story = generate_arabic_story(request.name, request.hobby, request.num_chapters, request.age)
        return {"story_text": story}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {str(e)}")

@app.post("/extract_scenes")
def extract_scenes(request: ExtractScenesRequest):
    """Extract scenes using text model."""
    try:
        scenes = fetch_story_scenes_from_api(request.arabic_story_text, request.num_scenes)
        return {"scenes": scenes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scene extraction failed: {str(e)}")

@app.post("/generate_single_image")
def generate_single_image(request: SingleImageRequest):
    """
    PROMPT STUDIO SAFEGUARD:
    Automated image generation is bypassed in the Prompt Studio workflow.
    Users manually copy prompts and attach references to external tools.
    """
    prompt = build_prompt(request.child_1st_name_arabic, request.scene_text_en, request.child_gender)
    
    # Check if automated image gen is bypassed (default: true)
    if os.getenv("DISABLE_IMAGE_GEN", "true").lower() == "true":
        return {
            "status": "bypassed",
            "message": "Automated image generation is bypassed in the Prompt Studio workflow. Please copy the main prompt and attach the specified references to generate manually in your external image tool.",
            "prompt": prompt
        }

    try:
        if not request.init_image_base64:
            raise ValueError("init_image_base64 is required.")
        img_data = base64.b64decode(request.init_image_base64)
        init_image = Image.open(io.BytesIO(img_data)).resize((1024, 1024))
        result_image = generate_scene_image(prompt, reference_image=init_image)

        buffered = io.BytesIO()
        result_image.save(buffered, format="PNG")
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt.encode('utf-8'))
        
        return Response(
            content=buffered.getvalue(), 
            media_type="image/png",
            headers={"X-Used-Prompt": encoded_prompt}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.post("/generate_quiz")
def generate_quiz(request: StoryQuizRequest):
    try:
        quiz_data = generate_story_quiz(request.story_text, request.age)
        return {"questions": quiz_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")

@app.post("/generate_audio")
def generate_audio_endpoint(request: AudioRequest):
    try:
        audio_content, media_type = generate_audio(request.text, request.chapter)
        return Response(content=audio_content, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {str(e)}")

@app.post("/render_story_viewer", response_class=HTMLResponse)
async def render_story_viewer(request: Request, data: RenderStoryRequest):
    try:
        return templates.TemplateResponse(
            "story_book.html",
            {
                "request": request, 
                "scenes": [scene.dict() for scene in data.scenes],
                "final_poster_url": data.final_poster_url
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render HTML story: {str(e)}")

# ======================
# Run directly with: python app.py
# ======================
if __name__ == "__main__":
    import uvicorn
    logger.info("===== Starting uvicorn server on 0.0.0.0:7860 =====")
    uvicorn.run(app, host="0.0.0.0", port=7860)
