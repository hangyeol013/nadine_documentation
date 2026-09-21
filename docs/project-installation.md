# Project Overview – Installation & Setup

This page explains what you need to install and configure before running Nadine.

---

## Prerequisites

### Hardware

- Intel RealSense camera (D400 series recommended)  
- Microphone for speech input  
- Speakers for audio output  

### Software

- Python 3.10 (control) and 3.11 (interaction and perception), installed through the conda environments below  
- [Conda](https://docs.conda.io/) (Anaconda/Miniconda)  
- [Docker](https://www.docker.com/) and Docker Compose (for the MQTT broker)  
- [Ollama](https://ollama.com/) as a systemd service  
- Two CUDA GPUs. The start script is written for 2× RTX 4090 and calls `nvidia-smi`, `pactl` (PulseAudio), and `gnome-terminal`  

### API Keys and Services

Two `.env` files hold the credentials; see the Environment Files section below and `docs/API_KEYS.md` in the repository for how to obtain each key:

- `control/.env` – Azure Speech (text-to-speech)  
- `interaction/.env` – Google Cloud (speech-to-text and translation), Serper (web search), and optional LangSmith tracing and OpenAI keys  

---

## Conda Environments

### 1. Clone the Repository

```bash
git clone <repository-url>
cd nadine_local
```

### 2. Set Up Conda Environments

**Control component**

```bash
cd control
conda env create -f environment.yml
conda activate nadine_new
```

**Interaction component**

```bash
cd interaction
conda env create -f environment.yml
conda activate nadine
# Or install via pip:
pip install -r requirements.txt
```

**Perception component**

```bash
cd perception
conda activate nadine  # Uses the interaction environment; there is no separate environment file
```

**Fine-tuned models**

The fine-tuned agents are served by Ollama, not by a separate server. Each LoRA adapter under `experiments/finetune/adapters/` is merged with `Qwen/Qwen2.5-1.5B-Instruct`, converted to a Q4_K_M GGUF file, and registered as an Ollama model from the matching Modelfile:

```bash
cd experiments/finetune/scripts/deployment
python export_to_ollama.py --agent all        # needs llama-cpp-python or a local llama.cpp build
ollama create nadine-intent_classifier -f exported/Modelfile.intent_classifier
# repeat for orchestration_agent, affective_appraisal, memory_update, episodic_memory, search_router
```

The exported GGUF files and Modelfiles are already in `experiments/finetune/exported/`, so on a machine that has them only the `ollama create` step is needed. Check that the `FROM` path in each Modelfile points at the GGUF file on your machine.

---

## MQTT Broker (EMQX)

From the project root:

```bash
docker volume create foo-emqx-data
docker volume create foo-emqx-log
docker compose up -d
```

The two volumes are declared as external in `compose.yaml`, so `docker compose up` fails until they exist. Compose also starts an `mqtt-monitor` container that logs every `nadine/#` message to `mqtt-monitor-logs/`.

The broker will be available at:

- MQTT: `localhost:1883`  
- Dashboard: `http://localhost:18083` (username: `admin`, password: `public`)

---

## Models

On first run, the system will automatically download required models. You can also pre-download:

- YOLOv8 face detection model `yolov8n-face.pt` (already placed in `perception/models/`).  
- OpenFace weights `MTL_backbone.pth` and `Alignment_RetinaFace.pth` in `perception/weights/` (used by the vision memory policy).  
- InsightFace `buffalo_s` and the Moondream2 scene-description model (downloaded automatically on first use).  
- LLM models via Ollama: `mistral-small3.2:latest`, `qwen2.5:1.5b-instruct`, `qwen2.5vl:3b`, and `nomic-embed-text` (knowledge RAG embeddings).  
- Fine-tuned models `nadine-intent_classifier`, `nadine-orchestration_agent`, `nadine-affective_appraisal`, `nadine-memory_update`, `nadine-episodic_memory`, and `nadine-search_router`, created in Ollama as described under Conda Environments.  

---

## Environment Files

### `control/.env`

Loaded by `control/main.py` at startup. Required for speech output:

```ini
AZURE_SERVICE_KEY=<azure_speech_key>
AZURE_SERVICE_REGION=westeurope
```

### `interaction/.env`

Loaded by the interaction layer. Required entries are Google Cloud and Serper; the rest are optional:

```ini
# Google Cloud (speech-to-text, translation)
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/interaction/google.json
GOOGLE_CLOUD_PROJECT=<your_gcp_project_id>

# Web search (Serper)
SERPER_API_KEY=<your_serper_api_key>

# LangSmith tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your_langsmith_api_key>

# OpenAI (optional; only needed if an agent is mapped to a profile with backend: openai)
# OPENAI_API_KEY=<your_openai_key>
```

Notes:

- `GOOGLE_APPLICATION_CREDENTIALS` must point to a service-account JSON key file with the Speech-to-Text and Translation APIs enabled; the repository expects it at `interaction/google.json`.  
- The default agent profiles run on local Ollama models and need no LLM key. `OPENAI_API_KEY` is only read when a profile sets `backend: openai` (the `gpt4o_mini` profiles), which no agent uses by default.  
- Omit `LANGCHAIN_TRACING_V2` and `LANGCHAIN_API_KEY` to disable tracing.  


