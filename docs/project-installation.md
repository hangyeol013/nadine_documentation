# Project Overview – Installation & Setup

This page explains what you need to install and configure before running Nadine.

---

## Prerequisites

### Hardware

- Intel RealSense camera (D400 series recommended)  
- Microphone for speech input  
- Speakers for audio output  

### Software

- Python 3.10  
- [Conda](https://docs.conda.io/) (Anaconda/Miniconda)  
- [Docker](https://www.docker.com/) and Docker Compose (for the MQTT broker)  
- CUDA-capable GPU (recommended for faster inference)  

### API Keys and Services

Create a `.env` file in the `interaction/` directory with:

- Azure TTS credentials  
- Google Cloud Speech API credentials  
- Google Cloud Translate API credentials  
- LLM API keys / configuration (e.g. for Ollama or other providers)  

---

## Conda Environments

### 1. Clone the Repository

```bash
git clone <repository-url>
cd nadine_Jan_2026
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
conda activate nadine  # Uses same environment as interaction
```

---

## MQTT Broker (EMQX)

From the project root:

```bash
docker compose up -d
```

The broker will be available at:

- MQTT: `localhost:1883`  
- Dashboard: `http://localhost:18083` (username: `admin`, password: `public`)

---

## Models

On first run, the system will automatically download required models. You can also pre-download:

- YOLOv8 face detection model (already placed in `perception/models/`).  
- InsightFace models (downloaded automatically on first use).  
- LLM models (configured via environment variables / Ollama / other backends).  

---

## Environment File (`interaction/.env`)

Before running the **interaction** layer, create an `.env` file in the `interaction/` directory.  
This file should contain the API keys and configuration for all external services used by Nadine:

```ini
# OpenAI / Azure OpenAI
OPENAI_API_KEY=<your_openai_key>              # If you call OpenAI models directly
azure_openai_endpoint=<https://...>.openai.azure.com/
azure_openai_api_key=<your_azure_openai_key>

# Google Cloud (STT, Translate, etc.)
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/google-credentials.json
GOOGLE_CLOUD_PROJECT=<your_gcp_project_id>

# Web search (Serper)
SERPER_API_KEY=<your_serper_api_key>

# LangChain / LangGraph observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your_langsmith_or_langchain_api_key>
```

Notes:

- `GOOGLE_APPLICATION_CREDENTIALS` should point to a JSON service-account key file with access to the required Google APIs.  
- If you are only using Azure OpenAI (and not OpenAI’s public API), you can leave `OPENAI_API_KEY` unset.  
- If you don’t want to use LangChain/LangGraph tracing, you can omit `LANGCHAIN_TRACING_V2` and `LANGCHAIN_API_KEY`.  


