# Perception Layer – Runtime & MQTT

This page describes how the perception runtime loop works and how it communicates with other layers over MQTT.

---

## Initialization (`main.py`)

On startup, `main.py`:

- **Logging & paths**
  - Initializes a shared logger via `LoggersFactory.getLogger()`.
  - Resolves `base_dir` (project root) and `USER_PROFILES_DIR` (`interaction/db/memory/user_profiles/`).

- **Configuration**
  - Loads `perception/config.yaml` via `load_perception_config()`.
  - Extracts `_mqtt_cfg`, `_yolo_cfg`, `_sm_cfg` for MQTT, YOLO, and selective memory.

- **MQTT client**
  - Creates a `paho.mqtt.client.Client`, assigns the callbacks, then connects to `_mqtt_cfg.primary_host` or `_mqtt_cfg.fallback_host` and starts the network loop in its own thread.
  - Subscribes to:
    - `nadine/face_recognition/user_info` – user info for face storage.
    - `nadine/perception/capture_current_view` – request for a one‑shot camera snapshot.
    - `nadine/affect/state` – Nadine's current affect, published by the interaction layer after each affective appraisal; drives the default memory policy.
  - Handlers only update shared variables; the camera pipeline is never touched from the MQTT thread.

- **RealSense camera**
  - Starts a RealSense `pipeline` with:
    - Color stream: `640x480`, 30 fps, BGR.
    - Depth stream: `640x480`, 30 fps.
  - Uses `rs.align(rs.stream.color)` so depth aligns with color.
  - If the camera fails to start (not connected, or claimed by another process), the process logs the error and exits.

- **Models**
  - YOLO face detector: `model_face = YOLO(_yolo_cfg["model_path"], ...)`.
  - InsightFace: `FaceAnalysis(name="buffalo_s")` with the detection and recognition modules, `det_size=(640, 640)`.

- **Face database**
  - Calls `load_known_faces(face_analyzer)`:
    - Iterates over each user in `USER_PROFILES_DIR`.
    - Loads existing face embeddings or derives them from stored face images.

- **Selective memory**
  - Reads `selective_memory.policy` from the config.
  - `pad_arousal` (default): creates a `PADArousalMemoryModule` with `arousal_threshold` (config value 0.25; code fallback 0.3). Loads only CLIP and Moondream2.
  - `vision`: creates a `SelectiveMemoryModule` with the OpenFace weights from `perception/weights/` and the emotion/novelty parameters from `_sm_cfg`.

---

## Per-Frame Loop

The main `while True` loop does, for each frame:

1. **Capture frames**
   - Wait for frames from RealSense with a 5 s timeout. On timeout the loop logs a warning and retries; it does not exit.
   - Align depth to color and extract:
     - `color_frame` → `color_image` (BGR `numpy` array).
     - `depth_frame` → `depth_image` (depth map).
   - If a snapshot was requested over MQTT, save the current frame to the requested path now.

2. **YOLO face detection & tracking**
   - Run `model_face.track(color_image, ..., conf=0.75)`.
   - For each detected face, collect:
     - Bounding box `(x1, y1, x2, y2)`.
     - Tracker ID.
     - Depth at the center of the box from `depth_frame`.

3. **Active user selection**
   - Among all detected faces, pick the one with **minimum positive depth** as the “active user”.
   - Maintain `tracked_user_id` and only update it if:
     - The closest face changes, or
     - More than ~2.5 seconds have passed since the last update.
   - If no face has been seen for 5 s (`NO_FACE_TIMEOUT`), clear the tracked user and, if a user had been announced, publish `nadine/graph/user_detected` with `{"user_name": null, "confidence": 0.0, "user_id": null}` so the interaction layer knows nobody is present.

4. **Face recognition**
   - If a `tracked_user_id` is set:
     - Run InsightFace detection on the full frame (`face_analyzer.get(color_image)`).
     - For each InsightFace detection, compute IoU with the YOLO bbox of the tracked user and keep the best match; it must have IoU above 0.2.
     - If that face has an embedding, compute cosine similarities to all `known_embeddings`.
     - `confidence` is reported as `(best_similarity + 1) / 2 * 100`, i.e. a percentage.
     - If the best similarity exceeds 0.3, set `name` and `user_id`; otherwise the user stays `"Unknown"`.

5. **3D position estimation**
   - For the tracked face, compute:
     - Center pixel `(cx, cy)` from the bounding box.
     - Depth at `(cx, cy)` from `depth_frame`.
     - 3D coordinates `coords_3d = rs2_deproject_pixel_to_point(...)`.
   - If coordinates are non‑zero, publish:

     - Topic: `nadine/agent/control/look_at`  
     - Payload: `{"x": coords_3d[0], "y": coords_3d[1], "z": coords_3d[2]}`

6. **User identity updates**
   - Every 5 seconds, or when the recognized name changes, publish:
     - Topic: `nadine/graph/user_detected`  
     - Payload: `{"user_name": name, "confidence": confidence, "user_id": user_id}`

7. **Selective memory hook**
   - Runs only for recognized users (`user_id` not `None`), at most once per `memorability_check_interval` seconds per user (config 3.0 s; code fallback 2.0 s), on a copy of the frame taken before anything is drawn on it.
   - **`pad_arousal` policy (default)**: read the latest `nadine/affect/state` values; compute `memorability = base[emotion_label] × intensity`; store if `should_store` is true (memorability ≥ `arousal_threshold`, or the user has no stored scenes yet).
   - **`vision` policy**: run OpenFace on a padded face crop, compute a CLIP embedding of the frame, and combine emotion salience and novelty into a memorability score; store if it is ≥ `memorability_threshold`.
   - Both policies then apply a 15 s per-user cooldown (`SCENE_STORE_COOLDOWN`): if a scene was stored for this user less than 15 s ago, the store is skipped.
   - On a store, a Moondream2 description is generated, the scene is written (see the Selective Memory page), and `nadine/memory/scene_stored` is published.

8. **Visualization**
   - For the tracked face only, draw the bounding box, the label `name (confidence%)`, and the 3D coordinates.
   - Show the window `"Face & 3D Tracking"`.

9. **Face storage**
   - When `nadine/face_recognition/user_info` has been received and the tracked face has an InsightFace match:
     - At most one face per user every 10 s (`FACE_STORE_COOLDOWN`), and only while the user has fewer than 3 stored face images.
     - `store_face_for_user(...)` writes the face crop and its embedding and publishes `nadine/graph/face_stored`.
     - Set a flag to reload `known_embeddings` on the next loop.

On exit (key `q` or exception), the pipeline is stopped, windows are closed, and the MQTT loop is stopped.

---

## MQTT Topics (Runtime Summary)

**Subscribed**

- `nadine/face_recognition/user_info`  
  - Payload: `{"user_name": "...", "user_id": "..."}`  
  - Purpose: instruct perception to store a face image + embedding for this user.

- `nadine/perception/capture_current_view`  
  - Payload: file path string  
  - Purpose: capture a single RGB frame and save it to the given path.

- `nadine/affect/state`  
  - Payload: `{"label": str, "arousal": float, "intensity": float}`  
  - Published by the interaction layer's affective appraisal node after every turn. The `pad_arousal` memory policy uses `label` and `intensity` to decide whether the current scene is memorable.

**Published**

- `nadine/agent/control/look_at`  
  - Payload: `{"x": float, "y": float, "z": float}`  
  - Used by the control layer to orient Nadine’s head/eyes toward the user.

- `nadine/graph/user_detected`  
  - Payload: `{"user_name": str, "confidence": float, "user_id": Optional[str]}`  
  - Used by the interaction layer to know who is in front of Nadine. All three fields are `null`/`0.0` when the tracked user has been absent for 5 s.

- `nadine/graph/face_stored`  
  - Payload: `{"user_name": str, "user_id": str, "status": "face_stored"}`  
  - Emitted after new face data has been persisted.

- `nadine/memory/scene_stored`  
  - Payload: `{"user_id": str, "user_name": str, "memorability": float, "emotion_label": str, "intensity": float, "description": str}`  
  - Under `pad_arousal`, `emotion_label` and `intensity` are the affect values that triggered the store. Under `vision`, `emotion_label` is the dominant facial emotion and `intensity` is the emotion salience.
  - No component in the interaction layer subscribes to this topic at present; it is available for monitoring and future use.

---

## Utilities

Perception reuses utilities from `perception/utils.py`:

- **`LoggersFactory`** – central logger for all perception logs.  
- **`user_info_init`** – initializes default `user_info.json` content for new users.
