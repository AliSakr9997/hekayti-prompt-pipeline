# Hekayti Prompt Pipeline & Character Identity Studio

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Hekayti (حكايتي)** is an AI-powered personalized Arabic storytelling platform for children.  
This repository houses the **Prompt Pipeline & Character Identity Studio** — the modern, production-grade engine responsible for ingesting Arabic story text, preserving character identity across illustrations, and generating structured, model-adapted prompt packs for state-of-the-art vision models (including Alibaba Cloud DashScope **Qwen-Image 2.0 Pro** and **Wan 2.7 Image Pro**).

---

## 🌟 Key Capabilities

1. **Child Identity & Avatar Modeling**
   - Encapsulates observable physical traits (hair style/color, skin tone, eye shape/color, unique markers like dimples).
   - Enforces canonical wardrobe and outfit consistency across all story pages.
   - Supports age-calibrated and gender-aware visual representation.

2. **Story Ingestion & Scene Planning**
   - Directly ingests Arabic story narrative output from the upstream Story Generation Model.
   - Decomposes the story into sequential, visually rich scene descriptions and cover art concepts.

3. **Multi-Angle Character Reference Sheets**
   - Synthesizes 3-angle character reference prompts (frontal portrait, 3/4 turn, full-body action) to maintain character visual consistency across models.

4. **Model-Specific Prompt Compilation**
   - Formats optimized prompts with negative tokens, composition guidance, lighting, and Arabic cultural aesthetics.
   - Native adapters for:
     - `qwen-image-2.0-pro`
     - `wan2.7-image-pro`
     - `wan2.7-image`

5. **Prompt Studio Web UI & Offline Fallback**
   - Modern, responsive Arabic-first web studio (`image-deploy/static/index.html`).
   - Integrated FastAPI service with real-time prompt compilation, consistency audits, and one-click ZIP prompt pack downloads.
   - Offline fallback mode: works smoothly without live API keys, generating fully structured prompt packs locally.

---

## 🏗️ Repository Architecture

```text
├── hekayti/                     # Core Python Prompt Studio & Identity Engine
│   ├── studio.py                # Main orchestration pipeline (PromptStudio)
│   ├── models.py                # Pydantic data schemas (ChildProfile, ScenePlan, PromptPack)
│   ├── prompting.py             # Prompt templates, style anchors & negative constraints
│   ├── providers.py             # DashScope / Qwen / Wan model integration
│   ├── qa.py                    # Automated consistency checks & audit rules
│   ├── image.py                 # Reference photo handling & base64 encoding
│   ├── metrics.py               # Prompt length & token metric tracking
│   ├── retry.py                 # Fallback & error handling strategies
│   └── experiments.py           # Experiment logging & benchmarking
├── image-deploy/                # FastAPI Production Deployment
│   ├── app.py                   # FastAPI application & API endpoints
│   ├── prompt_studio_engine.py  # Production prompt studio engine & DashScope caller
│   ├── model_utils.py           # Model helper routines
│   ├── static/index.html        # Interactive Prompt Studio Web UI
│   ├── templates/               # Story book HTML templates
│   ├── Dockerfile               # Container deployment configuration
│   └── requirements.txt         # Deployment dependencies
├── demo/                        # Standalone lightweight demo server & test assets
│   ├── server.py                # Zero-dependency local demo server
│   └── index.html               # Demo UI
├── docs/                        # Architecture & implementation audit specifications
├── competitive-analysis/        # Detailed competitive teardowns & benchmarks
├── HEKAYTI_PROMPT_AGENT.md      # Comprehensive technical specification & guidelines
├── generate_example_pack.py     # CLI tool to compile sample prompt packs
├── test_prompt_studio.py        # Complete test suite for prompt studio engine
├── test_wardrobe_prompt_only.py # Wardrobe consistency & offline mode tests
├── pyproject.toml               # Python project configuration
├── .env.example                 # Environment template
└── README.md
```

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/AliSakr9997/hekayti-prompt-pipeline.git
cd hekayti-prompt-pipeline
pip install -r image-deploy/requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and add your credentials if testing live API calls:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```
*(Note: If no API key is provided, the studio automatically switches to offline safe mode and generates structured prompt packs locally).*

### 3. Launching the Web UI

Run the FastAPI application:

```bash
cd image-deploy
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open your browser at:  
👉 **`http://localhost:8000/static/index.html`**

Or launch the standalone demo server:

```bash
python demo/server.py
```
👉 **`http://localhost:8080`**

---

## 🧪 Testing

Run the test suite to verify prompt generation, character anchoring, and offline fallback:

```bash
pytest test_prompt_studio.py -v
```

Run wardrobe and prompt-only mode verification:

```bash
pytest test_wardrobe_prompt_only.py -v
```

---

## 🔒 Security & Privacy

- **No Hardcoded Secrets**: All API keys and bearer tokens are loaded strictly via environment variables (`.env`) or session inputs.
- **Git Hygiene**: `.env` and all credential files are strictly ignored by `.gitignore`.
- **Children's Privacy**: Source reference photos are processed locally/in-memory and never permanently exposed in public artifacts.

---

## 📄 License

This project is licensed under the MIT License.
