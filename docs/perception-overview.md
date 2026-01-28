# Perception Layer – Overview

The perception layer senses and interprets the visual scene around Nadine.

If you are new to the project, start with **Project Overview**, then use this page to understand what the perception component does and how to run it.

---

## Responsibilities

- **Capture RGB‑D frames** from the Intel RealSense camera  
- **Detect and track faces** using [YOLOv8](https://docs.ultralytics.com/)  
- **Recognize known users** with [InsightFace](https://github.com/deepinsight/insightface) and a local face database  
- **Publish user position and identity** via MQTT to other layers  
- **Trigger visual memory updates**, delegating memorability decisions to the selective-memory module

---

## Files and Modules

Main perception files under `perception/`:

- **`main.py`**: main runtime loop (camera, detection, recognition, MQTT, selective memory integration).
- **`config.yaml`**: configuration for MQTT, YOLO face model, and selective memory (weights/thresholds).
- **`selective_memory.py`**: `SelectiveMemoryModule` class for computing memorability and writing memorable scenes.
- **`utils.py`**: logging (`LoggersFactory`) and `user_info_init` helper.
- **`run.sh`**: activates the `nadine` conda env and runs `main.py`.
- **`models/` and `weights/`**: model checkpoints for YOLO and [OpenFace](https://github.com/CMU-MultiComp-Lab/OpenFace-3.0)/OpenFace‑based models.

---

## How to Run

### Prerequisites

- **Environment**: `nadine` conda environment (from `interaction/environment.yml`).  
- **Hardware**: Intel RealSense RGB‑D camera connected and accessible.  
- **Services**: MQTT broker at `localhost` or `emqx` (default ports).  
- **Data layout**: interaction DB at `interaction/db/memory/user_profiles/` (created automatically as needed).

### Start command

From the project root:

```bash
cd /home/miralab/Development/nadine_Jan_2026
bash perception/run.sh
```

This will:

- Activate `nadine` conda env  
- Run `python3 perception/main.py`  
- Start RealSense, YOLO, InsightFace, MQTT, and selective memory integration

To stop, press **`q`** in the OpenCV window or interrupt the process with **`Ctrl+C`**.

---

## Configuration (`perception/config.yaml`)

Perception‑specific configuration lives under the `perception:` key:

- **`mqtt`**
  - `primary_host`, `fallback_host`, `port`, `keepalive`
- **`yolo_face`**
  - `model_path` (default `models/yolov8n-face.pt`)
  - `confidence` (detection threshold)
- **`selective_memory`**
  - `w_emotion`, `w_novelty`
  - `novelty_threshold`
  - `memorability_threshold`
  - `memorability_check_interval`

`main.py` loads this via `load_perception_config()` into `_mqtt_cfg`, `_yolo_cfg`, and `_sm_cfg`.

---

## Where to Go Next

- See **Perception Layer / Runtime & MQTT** for a step‑by‑step view of the frame loop and topic usage.  
- See **Perception Layer / Selective Memory** for details on memorability computation and scene storage.


