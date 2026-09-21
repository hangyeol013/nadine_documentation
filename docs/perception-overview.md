# Perception Layer – Overview

The perception layer senses and interprets the visual scene around Nadine.

If you are new to the project, start with **Project Overview**, then use this page to understand what the perception component does and how to run it.

---

## Responsibilities

- **Capture RGB‑D frames** from the Intel RealSense camera  
- **Detect and track faces** using [YOLOv8](https://docs.ultralytics.com/)  
- **Recognize known users** with [InsightFace](https://github.com/deepinsight/insightface) and a local face database  
- **Publish user position and identity** via MQTT to other layers  
- **Store memorable scenes** for each recognized user. Under the default policy the decision is driven by the affect state that the interaction layer publishes; under the fallback policy it is computed from facial emotion and scene novelty (see **Selective Memory**).

---

## Files and Modules

Main perception files under `perception/`:

- **`main.py`**: main runtime loop (camera, detection, recognition, MQTT, selective memory integration).
- **`config.yaml`**: configuration for MQTT, the YOLO face model, and the selective-memory policy and thresholds.
- **`selective_memory.py`**: `PADArousalMemoryModule` (default policy) and `SelectiveMemoryModule` (vision fallback) for deciding memorability and writing memorable scenes.
- **`utils.py`**: logging (`LoggersFactory`) and `user_info_init` helper.
- **`run.sh`**: activates the `nadine` conda env and runs `main.py`.
- **`models/`**: the YOLOv8 face checkpoint (`yolov8n-face.pt`). InsightFace's `buffalo_s` pack is downloaded automatically on first use.
- **`weights/`**: [OpenFace 3.0](https://github.com/CMU-MultiComp-Lab/OpenFace-3.0) weights (`MTL_backbone.pth`, `Alignment_RetinaFace.pth`, landmark files), used only by the `vision` memory policy.

---

## How to Run

### Prerequisites

- **Environment**: `nadine` conda environment (from `interaction/environment.yml`).  
- **Hardware**: Intel RealSense RGB‑D camera connected and accessible. `main.py` exits at startup if the camera cannot be opened.  
- **Services**: MQTT broker at `localhost` or `emqx` (default ports).  
- **Data layout**: interaction DB at `interaction/db/memory/user_profiles/` (created automatically as needed).

### Start command

`run.sh` runs `python3 main.py` with relative paths, so start it from the `perception/` directory:

```bash
cd /home/miralab/Development/nadine_local/perception
./run.sh
```

This will:

- Activate the `nadine` conda env  
- Run `python3 main.py`  
- Start RealSense, YOLO, InsightFace, MQTT, and the selective-memory module

In normal operation `start_nadine.sh` at the project root launches perception this way as its Step 2, after pre-warming the Ollama models, and waits 20 s for the perception models to load (see **Project Overview / Usage**).

To stop, press **`q`** in the OpenCV window or interrupt the process with **`Ctrl+C`**.

---

## Configuration (`perception/config.yaml`)

Perception‑specific configuration lives under the `perception:` key:

- **`mqtt`**
  - `primary_host`, `fallback_host`, `port`, `keepalive`
- **`yolo_face`**
  - `model_path` (default `models/yolov8n-face.pt`)
  - `confidence` – present in the file but currently not read; `main.py` calls the tracker with a hardcoded `conf=0.75`.
- **`selective_memory`**
  - `policy` – `"pad_arousal"` (default) or `"vision"`
  - `arousal_threshold` – used by the `pad_arousal` policy
  - `w_emotion`, `w_novelty`, `novelty_threshold`, `memorability_threshold`, `happy_boost_factor` – used by the `vision` policy
  - `memorability_check_interval` – seconds between memorability checks per user, both policies

`main.py` loads this via `load_perception_config()` into `_mqtt_cfg`, `_yolo_cfg`, and `_sm_cfg`.

---

## Where to Go Next

- See **Perception Layer / Runtime & MQTT** for a step‑by‑step view of the frame loop and topic usage.  
- See **Perception Layer / Selective Memory** for the two storage policies and the scene storage layout.
