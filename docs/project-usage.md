# Project Overview – Usage

This page explains how to start Nadine, both via the main script and per-component.

---

## Quick Start (`start_nadine.sh`)

From the project root:

```bash
./start_nadine.sh
```

This script will:

1. Set up audio echo cancellation and microphone volume.
2. Launch the **control** component (robot control server).
3. Start the **vLLM multi-LoRA server** on GPU 0 (serves fine-tuned Qwen2.5-1.5B adapters).
4. Wait for the vLLM server to become healthy (up to 90s).
5. Launch the **interaction** component on GPU 1 (dialogue system via Ollama + vLLM).
6. Launch the **perception** component on GPU 0 (face recognition + selective memory).

Make sure:

- All three conda environments are created: `nadine`, `nadine_new`, `vllm_serve` (see Installation & Setup).
- EMQX MQTT broker is running (see Installation & Setup).
- Ollama is running with required models (`mistral-small3.2`, `qwen2.5:1.5b-instruct`, `qwen2.5vl:3b`).

---

## Startup Options

`start_nadine.sh` supports several flags:

```bash
# Disable vision agent in the interaction graph
./start_nadine.sh --no-vision-agent

# Disable memory agents (NOTE: memory agents are disabled by default)
./start_nadine.sh --no-memory-agents

# Skip the perception process (no face recognition)
./start_nadine.sh --no-vision-process

# Set microphone volume (0-150%)
./start_nadine.sh --mic-volume=20
```

Default behavior: vision agent is **enabled**, memory agents are **disabled**, perception is **enabled**, mic volume is **20%**.

These are useful for debugging or running Nadine on systems without a camera or without GPU resources for vision.

---

## Manual Component Startup

You can also start each component separately.

### Control Component

```bash
cd control
conda activate nadine_new
./run.sh

# Or with custom paths:
python main.py -voicepath <path> -animationXMLPath <path>
```

### Interaction Component

```bash
cd interaction
conda activate nadine
./run.sh

# Or run without MQTT:
python -m nadine --nomqtt

# Or in chat mode (text-only only, no audio/UI):
python -m nadine --chatmode
```

### Perception Component

```bash
cd perception
conda activate nadine
./run.sh
```

Each component will log its status to its own `logs/` folder and communicate over MQTT as described in the layer-specific docs.


