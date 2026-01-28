# Perception Layer – Selective Memory

This page focuses on the **Selective Memory Module** (`selective_memory.py`), which decides which visual scenes are memorable enough to store for each user.

---

## Purpose

For every recognized user, the system occasionally evaluates the current visual scene and computes a **memorability score** based on:

- How emotionally salient the scene is  
- How novel the scene is compared to past scenes for that user  

If the memorability score is high enough, the scene is stored (image + embedding + metadata) in the user’s memory folder for later use by the interaction layer.

---

## Components

`SelectiveMemoryModule` combines three main pieces:

- **Emotion analysis (OpenFace)**
  - Uses OpenFace (`MultitaskPredictor` + `FaceDetector`) to infer probabilities over:
    - `['neutral', 'happy', 'sad', 'surprise', 'fear', 'disgust', 'anger', 'contempt']`
  - Produces a normalized probability distribution over these emotions.

- **Scene embedding (CLIP)**
  - Uses `openai/clip-vit-large-patch14` to embed the entire RGB frame into a high‑dimensional vector.
  - Embeddings are \(L_2\)-normalized for cosine similarity comparisons.

- **Scene description (optional VLM)**
  - Optionally uses `moondream2` to generate a short textual description for each stored scene.
  - If the model is unavailable, description generation is skipped gracefully.

All models are loaded once at initialization and run on the best available device (CUDA/MPS/CPU).

---

## Emotion & Novelty to Memorability

### Emotion salience

Given emotion probabilities \(p_e\) and thresholds \(t_e\) per emotion, salience is computed as:

\[
\text{salience}(p_e, t_e) = \max\left(0, \frac{p_e - t_e}{1 - t_e}\right)
\]

- Emotion thresholds are tuned per emotion (e.g., lower thresholds for “happy/sad”, higher for “surprise/disgust”).  
- The final **emotion salience** is the maximum salience value across active emotions:
  - Active set: `['happy', 'sad', 'surprise', 'fear', 'disgust', 'anger', 'contempt']`.

### Novelty

Novelty is based on **distance from past scenes** stored for the same user:

1. Compute CLIP embedding for the current frame.  
2. Load all previous embeddings for that user from:
   - `interaction/db/memory/user_profiles/<user_id>/memorable_scenes/embeddings/`
3. Compute cosine similarity between the current embedding and all stored embeddings:
   - Distance = \(1 - \text{similarity}\)
4. Define **novelty score** as the minimum distance (closest match); higher = more novel.

Novelty salience is then computed using the same threshold-based mapping as emotions:

\[
\text{novelty\_salience} = \max\left(0, \frac{\text{novelty\_score} - t_{\text{novelty}}}{1 - t_{\text{novelty}}}\right)
\]

Where \(t_{\text{novelty}}\) is `novelty_threshold` from config.

### Combined memorability

Memorability is a weighted sum of emotion and novelty salience:

\[
\text{memorability} = w_{\text{emotion}} \cdot \text{emotion\_salience}
                     + w_{\text{novelty}} \cdot \text{novelty\_salience}
\]

- Weights `w_emotion` and `w_novelty` are configured in `perception/config.yaml`.  
- If `memorability` ≥ `memorability_threshold`, the scene is stored.

---

## Storage Layout

For each user, memorable scenes are stored under:

`interaction/db/memory/user_profiles/<user_id>/memorable_scenes/`

Within that directory:

- **`images/`**  
  - Raw RGB images (no bounding boxes drawn).  
  - Filename: `scene_YYYYMMDD_HHMMSS.jpg`

- **`embeddings/`**  
  - Numpy `.npy` files with CLIP embeddings.  
  - Filename: `scene_YYYYMMDD_HHMMSS_embedding.npy`

- **`metadata/`**  
  - JSON files with metadata, including:
    - `scene_id`, `timestamp`, `image_path`
    - `memorability`, `emotion_salience`, `novelty_salience`
    - Full `emotion_probs`
    - Optional natural language `description`
  - Filename: `scene_YYYYMMDD_HHMMSS_metadata.json`

This structure lets downstream components (e.g., memory/RAG agents) quickly discover and use memorable scenes.

---

## Configuration Hooks

You can tune selective memory behavior via `perception/config.yaml`:

- `w_emotion`, `w_novelty` – balance between emotional and novelty cues.  
- `novelty_threshold` – how easily novelty becomes salient.  
- `memorability_threshold` – how “picky” the system is about storing scenes.  
- `memorability_check_interval` (in `main.py`) – how often memorability is evaluated per user.

For finer control (code changes), you can adjust:

- Per‑emotion thresholds in `SelectiveMemoryModule.emotion_thresholds`.  
- The way novelty is normalized or aggregated if you want more sophisticated behavior.


