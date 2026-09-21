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
2. Pre-warm the seven core Ollama models (Mistral Small 3.2, the five fine-tuned `nadine-*` models, and Qwen2.5-1.5B-Instruct) so they load onto GPU 1.
3. Launch the **perception** component on GPU 0 (face recognition + selective memory) and wait 20 s for its models to load.
4. Pre-warm the vision model `qwen2.5vl:3b`.
5. Launch the **interaction** component (dialogue system; uses the pre-warmed Ollama models).
6. Launch the **control** component (robot control server, no GPU models).

Make sure:

- The conda environments are created (see Installation & Setup).
- EMQX MQTT broker is running (see Installation & Setup).
- The Ollama service runs with `OLLAMA_MAX_LOADED_MODELS=10` and `CUDA_VISIBLE_DEVICES=1,0`, and has all required models: `mistral-small3.2`, `qwen2.5:1.5b-instruct`, `qwen2.5vl:3b`, `nomic-embed-text`, and the fine-tuned `nadine-*` models (see Installation & Setup).

---

## Startup Options

`start_nadine.sh` supports several flags:

```bash
# Skip the perception process (no face recognition)
./start_nadine.sh --no-vision-process

# Set microphone volume (0-150%)
./start_nadine.sh --mic-volume=20

# Accepted but no-ops with this script (see below)
./start_nadine.sh --no-vision-agent --no-memory-agents
```

The vision agent and the memory agents are controlled by the environment variables `NADINE_ENABLE_VISION_AGENT` and `NADINE_ENABLE_MEMORY_AGENTS`, which the script passes to the interaction process. Their defaults differ by entry point:

| Entry point | Vision agent | Memory agents |
|---|---|---|
| `./start_nadine.sh` | disabled | disabled |
| `./start_nadine_chatmode.sh` | enabled | enabled |
| `python -m nadine` run manually | enabled | enabled |

`start_nadine.sh` sets both to `0` and its `--no-vision-agent` and `--no-memory-agents` flags only set them to `0` again; there is no flag that enables them. To run the full graph from the main script, edit the two defaults at the top of the script or export the variables before launching the interaction component manually.

`--no-vision-process` is useful on systems without a camera or without GPU memory for the perception models.

---

## Chat Mode (`start_nadine_chatmode.sh`)

`start_nadine_chatmode.sh` launches the same components for text-based testing. It enables both agent groups by default and accepts:

```bash
./start_nadine_chatmode.sh [--no-vision-agent] [--no-memory-agents] [--no-vision-process] [--no-control]
```

`--no-control` skips the control layer, so no robot or serial port is needed. This script has no `--mic-volume` option.

---

## Manual Component Startup

You can also start each component separately.

### Control Component

```bash
cd control
./run.sh          # activates the nadine_new environment and runs main.py
```

`run.sh` passes no arguments; paths come from `control/config.yaml` (`animation_xml_path`, default `XMLAnimations`). `main.py` also accepts `-animationXMLPath <path>` and the legacy `-voicepath`, `-voicepathGerman`, and `-voicepathFrench` arguments, which are stored but no longer used since TTS is Azure.

### Interaction Component

```bash
cd interaction
./run.sh          # activates the nadine environment and runs python3 -m nadine

# Or run without MQTT:
python -m nadine --nomqtt

# Or in chat mode (text-only, no audio):
python -m nadine --chatmode
```

`run.sh` also registers a cleanup hook that stops every Ollama model the interaction layer uses when the terminal closes. When run manually, the vision and memory agents are enabled unless `NADINE_ENABLE_VISION_AGENT` or `NADINE_ENABLE_MEMORY_AGENTS` is set to `0`.

### Perception Component

```bash
cd perception
./run.sh          # activates the nadine environment and runs main.py
```

Run `run.sh` from inside each component directory: the scripts use relative paths for their config and model files.

Each component logs its status to its own `logs/` folder and communicates over MQTT as described in the layer-specific docs.

!!! note "Differences in the Hybrid Cloud version (nadine_phd)"
    The `start_nadine.sh` of `nadine_phd` accepts additional flags: `--no-visual-memory`, `--study` (per-session study logging; set `NADINE_PARTICIPANT_ID` first), and `--zoom-audio` (routes robot audio through a virtual device for remote sessions using `scripts/zoom_audio_setup.sh`). It passes further environment variables to perception (`NADINE_ENABLE_VISUAL_MEMORY`, `NADINE_STORAGE_EMOTION_SOURCE`, `NADINE_STORAGE_TRIGGER`, `NADINE_ENABLE_FER_SAMPLING`, `NADINE_FER_NOVELTY`, `NADINE_FER_INTERVAL`) and to interaction (`NADINE_STUDY_LOG`, `NADINE_PARTICIPANT_ID`). The pipeline mode is selected by `NADINE_PIPELINE_MODE` (`merged` or `legacy`), overriding `pipeline.mode` in the interaction config. Because its default agent profiles use the `openai` backend, `OPENAI_API_KEY` is required in `interaction/.env`; `ANTHROPIC_API_KEY` is only needed if a profile with `backend: anthropic` is mapped.


