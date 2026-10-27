"""Small local bridge between the demo UI and the installed Bailian CLI.

Credentials stay in Bailian's user config. This server never accepts or logs
an API key and only exposes the local demo endpoints.
"""

from __future__ import annotations

import json
import mimetypes
import shutil
import time
import subprocess
import uuid
import base64
import hashlib
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from hekayti.studio import story_hash
from hekayti.models import CharacterProfile, CharacterSceneState, Scene, Strategy, Wardrobe
from hekayti.prompting import PromptCompiler


ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated"
EXPERIMENTS = ROOT / "experiments"
HOST = "127.0.0.1"
PORT = 8000
IMAGE_MODELS = {
    "qwen-image-3.0",
    "qwen-image-3.0-pro",
    "qwen-image-2.1-pro",
    "qwen-image-2.1-turbo",
    "qwen-mt-image-2.0",
    "wan2.6-t2i",
    "wanx2.1-t2i-plus",
    "wanx2.0-t2i-turbo",
}
PROMPT_ONLY_MODE = True
EXPERIMENT_IMAGE_MODEL = "qwen-image-2.1-turbo"
VISION_MODEL = "qwen3-vl-plus"
REFERENCE_INTERFACE_SUPPORTED = True
REFERENCE_INTERFACE_LIMITATION = (
    "The installed Bailian CLI wrapper cannot send local references, so the harness uses "
    "the documented DashScope multimodal-generation endpoint directly with Base64 image data."
)


def run_bailian(args: list[str], timeout: int = 240) -> str:
    executable = shutil.which("bl.cmd") or shutil.which("bl") or "bl"
    command = [executable, *args, "--output", "json", "--quiet"]
    last_error = "Bailian CLI failed"
    for attempt in range(2):
        try:
            result = subprocess.run(
                command,
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            last_error = result.stderr.strip() or result.stdout.strip() or last_error
        except subprocess.TimeoutExpired as error:
            last_error = f"Bailian CLI timed out: {error}"
        if attempt == 0:
            time.sleep(2)
    raise RuntimeError(last_error)


def parse_json_output(output: str) -> object:
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return output


def bailian_credentials() -> tuple[str, str]:
    config_path = Path.home() / ".bailian" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    if not isinstance(api_key, str) or not api_key:
        raise RuntimeError("Bailian API key is not configured")
    if not isinstance(base_url, str) or not base_url:
        raise RuntimeError("Bailian base URL is not configured")
    return api_key, base_url.rstrip("/")


def image_data_uri(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"reference image does not exist: {path}")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError(f"reference image exceeds 10 MB: {path.name}")
    mime = mimetypes.guess_type(path.name)[0]
    if not mime or not mime.startswith("image/"):
        raise ValueError(f"unsupported reference image type: {path.name}")
    if dimensions_for(path) is None:
        raise ValueError(f"reference image is not a valid PNG or JPEG: {path.name}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def direct_reference_generate(
    *,
    model: str,
    prompt: str,
    references: list[Path],
    output_dir: Path,
    output_prefix: str,
) -> dict[str, object]:
    """Call the documented DashScope multimodal image endpoint directly."""
    if not references:
        raise ValueError("at least one image reference is required")
    if len(references) > 10:
        raise ValueError("qwen-image-2.1 supports at most 10 references")
    api_key, base_url = bailian_credentials()
    content = [{"image": image_data_uri(path)} for path in references]
    content.append({"text": prompt})
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {"prompt_extend": False},
    }
    endpoint = f"{base_url}/api/v1/services/aigc/multimodal-generation/generation"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"DashScope reference request failed ({error.code}): {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"DashScope reference request failed: {error.reason}") from error
    try:
        output_content = result["output"]["choices"][0]["message"]["content"]
        image_url = next(item["image"] for item in output_content if "image" in item)
    except (KeyError, IndexError, StopIteration, TypeError) as error:
        raise RuntimeError(f"DashScope response did not contain an output image: {result}") from error
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_prefix}.png"
    download = urllib.request.Request(image_url, headers={"User-Agent": "Hekayti-local-experiment/1.0"})
    with urllib.request.urlopen(download, timeout=360) as response:
        output_path.write_bytes(response.read())
    return {
        "output_path": str(output_path),
        "provider": "dashscope-direct",
        "endpoint": endpoint,
        "model": model,
        "reference_count": len(references),
        "references": [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in references
        ],
        "request_id": result.get("request_id"),
        "usage": result.get("usage"),
    }


def dimensions_for(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[index:index + 2], "big")
            if marker in range(0xC0, 0xC4) and index + 7 < len(data):
                return int.from_bytes(data[index + 5:index + 7], "big"), int.from_bytes(data[index + 3:index + 5], "big")
            index += length
    return None


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def local_asset_url(path: Path | str) -> str:
    try:
        relative = Path(path).resolve().relative_to(ROOT)
    except ValueError:
        return ""
    return "/" + str(relative).replace("\\", "/")


def extract_multipart(body: bytes, content_type: str) -> tuple[str, bytes]:
    boundary = content_type.split("boundary=", 1)[-1].strip().strip('"').encode()
    for part in body.split(b"--" + boundary):
        if b"\r\n\r\n" not in part:
            continue
        headers, content = part.split(b"\r\n\r\n", 1)
        if b'filename="' not in headers:
            continue
        filename = headers.split(b'filename="', 1)[1].split(b'"', 1)[0].decode("utf-8", "replace")
        return Path(filename).name or "source-image", content.rstrip(b"\r\n-")
    raise ValueError("multipart request did not contain an image file")


class Handler(BaseHTTPRequestHandler):
    server_version = "HekaytiDemo/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            try:
                auth = parse_json_output(run_bailian(["auth", "status"]))
                self.send_json(200, {"authenticated": bool(isinstance(auth, dict) and auth.get("authenticated"))})
            except Exception as error:
                self.send_json(503, {"authenticated": False, "error": str(error)})
            return
        if path == "/api/experiments":
            runs = []
            if EXPERIMENTS.is_dir():
                for run_dir in sorted(EXPERIMENTS.glob("run_*"), reverse=True):
                    summary_path = run_dir / "summary.json"
                    if summary_path.is_file():
                        runs.append(json.loads(summary_path.read_text(encoding="utf-8")))
            self.send_json(200, {"runs": runs})
            return
        if path == "/api/quota":
            if PROMPT_ONLY_MODE:
                self.send_json(200, {"models": [], "disabled": True, "message": "Image-generation quota is protected; prompt-only mode is enabled."})
                return
            try:
                raw = parse_json_output(run_bailian(["usage", "free"], timeout=60))
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
                    and item.get("model") in IMAGE_MODELS
                ]
                self.send_json(200, {"models": models})
            except Exception as error:
                self.send_json(503, {"models": [], "error": str(error)})
            return
        self.serve_file(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/upload-photo":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                filename, content = extract_multipart(self.rfile.read(length), self.headers.get("Content-Type", ""))
                character_id = self.headers.get("X-Character-Id", "character-1")
                run_dir = EXPERIMENTS / "current" / "characters" / character_id / "source_photos"
                run_dir.mkdir(parents=True, exist_ok=True)
                destination = run_dir / f"{uuid.uuid4().hex[:10]}-{filename}"
                destination.write_bytes(content)
                dimensions = dimensions_for(destination)
                record = {
                    "character_id": character_id,
                    "path": str(destination.relative_to(ROOT.parent)),
                    "filename": filename,
                    "bytes": len(content),
                    "dimensions": dimensions,
                }
                save_json(destination.with_suffix(".json"), record)
                self.send_json(200, record)
            except Exception as error:
                self.send_json(400, {"error": str(error)})
            return
        if path == "/api/evaluation":
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
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
                evaluation_path = EXPERIMENTS / run_id / "evaluation.json"
                save_json(evaluation_path, data)
                self.send_json(200, {
                    "saved": str(evaluation_path.relative_to(ROOT.parent)),
                    "aggregates": aggregates,
                    "recommendation": data["recommendation"],
                })
            except Exception as error:
                self.send_json(400, {"error": str(error)})
            return
        if path == "/api/profile":
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                result = create_profile(data)
                self.send_json(200, result)
            except Exception as error:
                self.send_json(502, {"error": str(error)})
            return
        if path == "/api/plan-story":
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                result = plan_story(data)
                self.send_json(200, result)
            except Exception as error:
                self.send_json(502, {"error": str(error)})
            return
        if path == "/api/experiment":
            if PROMPT_ONLY_MODE:
                self.send_json(403, {"error": "Prompt-only mode is enabled. Export prompts and test images manually, then import results for evaluation."})
                return
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                result = run_experiment(data)
                self.send_json(200, result)
            except Exception as error:
                self.send_json(502, {"error": str(error)})
            return
        if path == "/api/compile-prompt":
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                self.send_json(200, compile_prompt_only(data))
            except Exception as error:
                self.send_json(400, {"error": str(error)})
            return
        if path != "/api/generate":
            self.send_json(404, {"error": "not found"})
            return
        try:
            if PROMPT_ONLY_MODE:
                raise PermissionError("Prompt-only mode is enabled; no image-generation API calls are permitted.")
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            result = generate(data)
            self.send_json(200, result)
        except Exception as error:
            self.send_json(502, {"error": str(error)})

    def serve_file(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        file_path = (ROOT / relative).resolve()
        if ROOT not in file_path.parents and file_path != ROOT:
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def generate(data: dict[str, object]) -> dict[str, object]:
    name = str(data.get("name") or "Character").strip()
    age = str(data.get("age") or "child").strip()
    appearance = str(data.get("appearance") or "consistent appearance").strip()
    wardrobe = str(data.get("wardrobe") or "").strip()
    action = str(data.get("action") or "standing naturally").strip()
    expression = str(data.get("expression") or "happy").strip()
    arabic = str(data.get("arabic") or "").strip()
    strategy = str(data.get("strategy") or "hybrid").strip()
    model = str(data.get("model") or "qwen-image-3.0").strip()
    if model not in IMAGE_MODELS:
        raise ValueError("Unsupported image model")

    planner_prompt = (
        "Return one concise English sentence describing the visual scene direction for this "
        "children's illustration. Do not mention prompts, APIs, or JSON. Preserve the named "
        f"character and action. Character: {name}, {age}; appearance: {appearance}; "
        f"outfit: {wardrobe}; action: {action}; expression: {expression}; Arabic text: {arabic}."
    )
    planner_raw = run_bailian([
        "text", "chat", "--model", "qwen3.8-max",
        "--message", planner_prompt, "--max-tokens", "80", "--temperature", "0",
    ], timeout=120)
    planner_result = parse_json_output(planner_raw)
    if isinstance(planner_result, dict):
        output = planner_result.get("output") or {}
        planner_text = str(output.get("text") or output.get("choices") or "").strip()
    else:
        planner_text = str(planner_result or "").strip()
    prompt = (
        "A warm colorful children's storybook illustration in a gentle editorial watercolor style. "
        f"Character: {name}, a {age}, with {appearance}. "
        f"Wardrobe: {wardrobe}. Action: {action}; expression: {expression}. "
        "Environment: a colorful garden with flowers and soft daylight. "
        f"Scene direction: {planner_text.strip()} "
        f"Identity conditioning strategy: {strategy}. Preserve distinctive hairstyle and facial features. "
        "No extra characters, text, logos, watermark, or distorted hands."
    )
    negative = "extra characters, text, watermark, distorted hands"
    GENERATED.mkdir(exist_ok=True)
    prefix = f"hekayti-live-{int(time.time())}"
    image_raw = run_bailian([
        "image", "generate", "--model", model,
        "--prompt", prompt, "--negative-prompt", negative,
        "--size", "1024*1024", "--prompt-extend", "false",
        "--out-dir", str(GENERATED), "--out-prefix", prefix,
    ], timeout=360)
    image_result = parse_json_output(image_raw)
    image_path = next(GENERATED.glob(f"{prefix}.*"), None)
    if image_path is None:
        raise RuntimeError(f"Image generation returned no local file: {image_result}")
    return {
        "image": f"/generated/{image_path.name}",
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative,
        "planner": planner_text.strip(),
        "strategy": strategy,
    }


def compile_prompt_only(data: dict[str, object]) -> dict[str, object]:
    """Compile a structured prompt locally; this function performs no network calls."""
    wardrobe_data = data.get("wardrobe") if isinstance(data.get("wardrobe"), dict) else {}
    wardrobe = Wardrobe(
        top=str(wardrobe_data.get("top", "")), outerwear=str(wardrobe_data.get("outerwear", "")),
        bottom=str(wardrobe_data.get("bottom", "")), dress=str(wardrobe_data.get("dress", "")),
        shoes=str(wardrobe_data.get("shoes", "")), accessories=tuple(str(x) for x in wardrobe_data.get("accessories", []) if str(x).strip()),
        mode=str(wardrobe_data.get("mode", "preferred")),
    )
    character = CharacterProfile.create(
        id="character-1", name=str(data.get("name") or "Child"), age=str(data.get("age") or "child"),
        appearance=tuple(str(x) for x in data.get("appearance", ["consistent facial features"])),
        wardrobe_config=wardrobe, negative_constraints=("extra characters", "text", "watermark", "identity drift"),
    )
    state = CharacterSceneState(character_id="character-1", action=str(data.get("action") or "standing naturally"),
                                expression=str(data.get("expression") or "happy"),
                                mandatory_costume=str(data.get("mandatory_costume")) if data.get("mandatory_costume") else None)
    scene = Scene.create(id="scene-1", description=str(data.get("scene") or "A storybook scene"), setting=str(data.get("setting") or "a colorful setting"),
                         character_ids=["character-1"], character_states=[state], reference_asset_ids=[str(x) for x in data.get("references", [])])
    compiled = PromptCompiler(Strategy(str(data.get("strategy") or "hybrid"))).compile(scene, {"character-1": character})
    return {"prompt_only": True, "positive": compiled.positive, "negative": compiled.negative, "reference_ids": compiled.reference_ids,
            "strategy": compiled.strategy.value, "sections": compiled.sections}


def create_profile(data: dict[str, object]) -> dict[str, object]:
    photo = Path(str(data.get("photo_path", "")))
    if not photo.is_file():
        raise ValueError("photo_path must point to a local uploaded photo")
    prompt = (
        "Describe only visually observable identity traits in this child photo. Return JSON with "
        "face_shape, hair_color, hair_style, skin_tone, eye_color, distinctive_features, "
        "body_proportions, and clothing. Use null or [] when not discernible; do not guess."
    )
    raw = parse_json_output(run_bailian([
        "vision", "describe", "--image", str(photo), "--model", VISION_MODEL,
        "--prompt", prompt,
    ], timeout=180))
    profile = {
        "character_id": str(data.get("character_id") or "character-1"),
        "source_photo": str(photo),
        "model": VISION_MODEL,
        "candidate": raw,
        "status": "candidate",
    }
    save_json(EXPERIMENTS / "current" / "characters" / profile["character_id"] / "profile.json", profile)
    return profile


def plan_story(data: dict[str, object]) -> dict[str, object]:
    story = str(data.get("story_ar") or "").strip()
    if not story:
        raise ValueError("story_ar is required")
    character_id = str(data.get("character_id") or "character-1")
    prompt = (
        "Convert the Arabic story below into a JSON array of about 10 scenes. Preserve every "
        "scene_text_ar exactly. Each item must have scene_id, scene_text_ar, characters (array "
        "with character_id, action, pose, expression), environment, props (array), camera, mood, "
        "and continuity_requirements (array). Use only the supplied character ID and do not invent "
        "characters. Return JSON only.\nCharacter ID: " + character_id + "\nStory:\n" + story
    )
    last = ""
    for attempt in range(2):
        raw = parse_json_output(run_bailian([
            "text", "chat", "--model", "qwen3.8-max", "--message", prompt,
            "--max-tokens", "4000", "--temperature", "0",
        ], timeout=180))
        last = raw
        text = raw
        if isinstance(raw, dict):
            output = raw.get("output") or {}
            text = output.get("text") or output.get("choices") or ""
        if isinstance(text, str):
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            try:
                scenes = json.loads(text)
            except json.JSONDecodeError:
                scenes = None
        else:
            scenes = text
        if isinstance(scenes, list) and scenes and all(validate_scene(item, character_id) for item in scenes):
            result = {
                "story_ar": story,
                "story_source_hash": story_hash(story),
                "story_version": int(data.get("story_version") or 1),
                "character_id": character_id,
                "scenes": scenes,
                "attempts": attempt + 1,
            }
            save_json(EXPERIMENTS / "current" / "story.json", result)
            return result
        prompt += "\nYour previous output was invalid. Return only the required JSON array."
    raise ValueError(f"Scene planning failed validation after 2 attempts: {last}")


def validate_scene(scene: object, character_id: str) -> bool:
    if not isinstance(scene, dict):
        return False
    required = {"scene_id", "scene_text_ar", "characters", "environment", "props", "camera", "mood", "continuity_requirements"}
    if not required.issubset(scene):
        return False
    if not isinstance(scene["characters"], list) or not scene["characters"]:
        return False
    return all(isinstance(item, dict) and item.get("character_id") == character_id and item.get("action") for item in scene["characters"])


def run_experiment(data: dict[str, object]) -> dict[str, object]:
    scenes = data.get("scenes")
    photo_paths = [Path(str(item)) for item in data.get("photo_paths", [])]
    source_story_ar = str(data.get("story_ar") or "").strip()
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list")
    if not photo_paths or not all(path.is_file() for path in photo_paths):
        raise ValueError("at least one local source photo is required")
    run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    run_dir = EXPERIMENTS / run_id
    save_json(run_dir / "config.json", {
        "image_model": EXPERIMENT_IMAGE_MODEL,
        "conditioning_interface": "DashScope multimodal-generation with Base64 image references",
        "conditioning_supported": REFERENCE_INTERFACE_SUPPORTED,
        "limitation": REFERENCE_INTERFACE_LIMITATION if not REFERENCE_INTERFACE_SUPPORTED else None,
        "photo_paths": [str(path) for path in photo_paths],
        "strategies": ["sheet", "photos", "hybrid"],
        "story_source_hash": story_hash(source_story_ar) if source_story_ar else None,
        "scene_count": len(scenes),
    })
    save_json(run_dir / "story.json", {
        "source_text_ar": source_story_ar,
        "source_hash": story_hash(source_story_ar) if source_story_ar else None,
        "scenes": scenes,
    })
    results = []
    if not REFERENCE_INTERFACE_SUPPORTED:
        for scene in scenes:
            for strategy in ("arm_a_sheet", "arm_b_photos", "arm_c_hybrid"):
                scene_dir = run_dir / "scenes" / str(scene.get("scene_id", "scene")) / strategy
                scene_dir.mkdir(parents=True, exist_ok=True)
                refs = [str(path) for path in photo_paths] if strategy != "arm_a_sheet" else []
                prompt = compile_experiment_prompt(scene)
                save_json(scene_dir / "request.json", {
                    "provider": "bailian-cli",
                    "model": EXPERIMENT_IMAGE_MODEL,
                    "prompt": prompt,
                    "references": refs,
                    "strategy": strategy,
                    "conditioning_supported": False,
                })
                (scene_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
                metrics = {
                    "success": False,
                    "status": "unsupported",
                    "error": REFERENCE_INTERFACE_LIMITATION,
                    "duration_seconds": 0,
                    "references_sent": refs,
                }
                save_json(scene_dir / "metrics.json", metrics)
                results.append({
                    "scene_id": scene.get("scene_id"),
                    "strategy": strategy,
                    "prompt": prompt,
                    "reference_urls": [local_asset_url(path) for path in refs if local_asset_url(path)],
                    **metrics,
                })
        summary = {
            "run_id": run_id,
            "image_model": EXPERIMENT_IMAGE_MODEL,
            "conditioning_supported": False,
            "limitation": REFERENCE_INTERFACE_LIMITATION,
            "results": results,
        }
        save_json(run_dir / "summary.json", summary)
        return summary
    sheet = run_dir / "characters" / "character-1" / "character_sheet.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    try:
        direct_reference_generate(
            model=EXPERIMENT_IMAGE_MODEL,
            references=[photo_paths[0]],
            prompt="Create a clean multi-view children's storybook character sheet preserving this child's observable identity. Plain background, no text.",
            output_dir=sheet.parent,
            output_prefix="character-sheet",
        )
    except Exception as caught:
        limitation = f"{REFERENCE_INTERFACE_LIMITATION} Initial reference generation failed: {caught}"
        results = []
        for scene in scenes:
            for strategy in ("arm_a_sheet", "arm_b_photos", "arm_c_hybrid"):
                scene_dir = run_dir / "scenes" / str(scene.get("scene_id", "scene")) / strategy
                scene_dir.mkdir(parents=True, exist_ok=True)
                prompt = compile_experiment_prompt(scene)
                refs = [str(path) for path in photo_paths]
                metrics = {
                    "success": False,
                    "status": "unsupported",
                    "error": limitation,
                    "duration_seconds": 0,
                    "references_sent": [str(path) for path in photo_paths],
                }
                save_json(scene_dir / "metrics.json", metrics)
                results.append({
                    "scene_id": scene.get("scene_id"),
                    "strategy": strategy,
                    "prompt": prompt,
                    "reference_urls": [local_asset_url(path) for path in refs if local_asset_url(path)],
                    **metrics,
                })
        summary = {
            "run_id": run_id,
            "image_model": EXPERIMENT_IMAGE_MODEL,
            "conditioning_supported": False,
            "limitation": limitation,
            "results": results,
        }
        save_json(run_dir / "summary.json", summary)
        return summary
    generated_sheet = sheet.parent / "character-sheet.png"
    if generated_sheet.is_file() and generated_sheet != sheet:
        generated_sheet.rename(sheet)
    save_json(run_dir / "characters" / "character-1" / "profile.json", {
        "source_photos": [str(path) for path in photo_paths],
        "sheet": str(sheet) if sheet.is_file() else None,
        "model": EXPERIMENT_IMAGE_MODEL,
    })
    for scene in scenes:
        for strategy, refs in (
            ("arm_a_sheet", [sheet] if sheet.is_file() else []),
            ("arm_b_photos", photo_paths),
            ("arm_c_hybrid", ([sheet] if sheet.is_file() else []) + photo_paths),
        ):
            scene_dir = run_dir / "scenes" / str(scene.get("scene_id", "scene")) / strategy
            scene_dir.mkdir(parents=True, exist_ok=True)
            prompt = compile_experiment_prompt(scene)
            request = {
                "provider": "dashscope-direct",
                "model": EXPERIMENT_IMAGE_MODEL,
                "prompt": prompt,
                "references": [str(path) for path in refs],
                "strategy": strategy,
                "dimensions": "1024*1024",
                "prompt_extend": False,
                "reference_interface": "multimodal-generation",
            }
            save_json(scene_dir / "request.json", request)
            (scene_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
            started = time.time()
            error = None
            try:
                if not refs:
                    raise RuntimeError("character sheet was not generated")
                provider_result = direct_reference_generate(
                    model=EXPERIMENT_IMAGE_MODEL,
                    references=refs,
                    prompt=prompt,
                    output_dir=scene_dir,
                    output_prefix="result",
                )
                request["provider_result"] = {
                    key: value for key, value in provider_result.items()
                    if key != "output_path"
                }
            except Exception as caught:
                error = str(caught)
            metrics = {
                "success": error is None,
                "error": error,
                "duration_seconds": round(time.time() - started, 3),
                "references_sent": [str(path) for path in refs],
            }
            if error is None:
                metrics["provider_result"] = request["provider_result"]
                save_json(scene_dir / "request.json", request)
            save_json(scene_dir / "metrics.json", metrics)
            results.append({
                "scene_id": scene.get("scene_id"),
                "strategy": strategy,
                "prompt": prompt,
                "reference_urls": [local_asset_url(path) for path in refs if local_asset_url(path)],
                **metrics,
            })
    summary = {"run_id": run_id, "image_model": EXPERIMENT_IMAGE_MODEL, "results": results}
    save_json(run_dir / "summary.json", summary)
    return summary


def compile_experiment_prompt(scene: dict[str, object]) -> str:
    characters = "; ".join(
        f"{item.get('character_id')}: {item.get('action')}, pose {item.get('pose')}, expression {item.get('expression')}"
        for item in scene.get("characters", [])
    )
    return (
        f"Children's storybook illustration. Preserve the original scene meaning: {scene.get('scene_text_ar')}. "
        f"Characters: {characters}. Environment: {scene.get('environment')}. "
        f"Props: {', '.join(scene.get('props', []))}. Camera: {scene.get('camera')}. "
        f"Mood: {scene.get('mood')}. Continuity: {', '.join(scene.get('continuity_requirements', []))}. "
        "Preserve identity from the supplied reference images. No extra characters, text, logos, or watermark."
    )


if __name__ == "__main__":
    print(f"Hekayti AI demo: http://{HOST}:{PORT}/")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
