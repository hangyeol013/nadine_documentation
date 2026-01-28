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
  - Creates a `paho.mqtt.client.Client`.
  - Connects to `_mqtt_cfg.primary_host` or `_mqtt_cfg.fallback_host`.
  - Subscribes to:
    - `nadine/face_recognition/user_info` – user info for face storage.
    - `nadine/perception/capture_current_view` – request for a one‑shot camera snapshot.

- **RealSense camera**
  - Starts a RealSense `pipeline` with:
    - Color stream: `640x480`, 30 fps, BGR.
    - Depth stream: `640x480`, 30 fps.
  - Uses `rs.align(rs.stream.color)` so depth aligns with color.

- **Models**
  - YOLO face detector: `model_face = YOLO(_yolo_cfg["model_path"], ...)`.
  - InsightFace: `FaceAnalysis` with detection + recognition.

- **Face database**
  - Calls `load_known_faces(face_analyzer)`:
    - Iterates over each user in `USER_PROFILES_DIR`.
    - Loads existing face embeddings or derives them from stored face images.

- **Selective memory**
  - Creates a `SelectiveMemoryModule` with:
    - OpenFace backbone and face detector weights (`perception/weights/`).
    - Weights/thresholds from `_sm_cfg` (emotion, novelty, memorability).

---

## Per-Frame Loop

The main `while True` loop does, for each frame:

1. **Capture frames**
   - Wait for frames from RealSense.
   - Align depth to color and extract:
     - `color_frame` → `color_image` (BGR `numpy` array).
     - `depth_frame` → `depth_image` (depth map).

2. **YOLO face detection & tracking**
   - Run `model_face.track(color_image, ...)`.
   - For each detected face, collect:
     - Bounding box `(x1, y1, x2, y2)`.
     - Tracker ID.
     - Depth at the center of the box from `depth_frame`.

3. **Active user selection**
   - Among all detected faces, pick the one with **minimum positive depth** as the “active user”.
   - Maintain `tracked_user_id` and only update it if:
     - The closest face changes, or
     - More than ~2.5 seconds have passed since the last update.

4. **Face recognition**
   - If a `tracked_user_id` is set:
     - Run InsightFace detection (`face_analyzer.get(color_image)`).
     - For each InsightFace detection, compute IoU with the YOLO bbox of the tracked user.
     - Pick the best IoU match and, if an embedding is available:
       - Compute cosine similarities to all `known_embeddings`.
       - If the best similarity passes threshold, set:
         - `name` (user name),
         - `user_id`,
         - `confidence` (%).

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
   - For recognized users (`user_id` not `None`), periodically (per user):
     - Compute emotion probabilities from the full frame.
     - Compute a CLIP embedding for scene novelty.
     - Ask `SelectiveMemoryModule` for a memorability score.
     - If memorability exceeds threshold, store the scene and publish an event (see the Selective Memory page for details).

8. **Visualization**
   - Draw the face bounding box, label with `name (confidence%)` and the 3D coordinates.
   - Show the window `"Face & 3D Tracking"`.

9. **Face storage**
   - When `nadine/face_recognition/user_info` is received:
     - Call `store_face_for_user(...)` to store image and embeddings for that user.
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

**Published**

- `nadine/agent/control/look_at`  
  - Payload: `{"x": float, "y": float, "z": float}`  
  - Used by the control layer to orient Nadine’s head/eyes toward the user.

- `nadine/graph/user_detected`  
  - Payload: `{"user_name": str, "confidence": float, "user_id": Optional[str]}`  
  - Used by the interaction layer to know who is in front of Nadine.

- `nadine/graph/face_stored`  
  - Payload: `{"user_name": str, "user_id": str, "status": "face_stored"}`  
  - Emitted after new face data has been persisted.

- `nadine/memory/scene_stored`  
  - Payload: user ID/name, memorability metrics, and optional description  
  - Emitted after a memorable scene is stored by the selective memory module.

---

## Utilities

Perception reuses utilities from `perception/utils.py`:

- **`LoggersFactory`** – central logger for all perception logs.  
- **`user_info_init`** – initializes default `user_info.json` content for new users.


