# Perception Layer – Selective Memory

This page focuses on the **selective memory module** (`selective_memory.py`), which decides which visual scenes are memorable enough to store for each user.

---

## Purpose

For every recognized user, the system periodically evaluates the current visual scene and decides whether to keep it. A kept scene is stored as image + CLIP embedding + metadata in the user's memory folder, together with a short natural-language description, for later retrieval by the interaction layer.

Two storage policies are implemented and selected with `selective_memory.policy` in `perception/config.yaml`:

- **`pad_arousal`** (default) – the decision comes from Nadine's own affective state, as appraised by the interaction layer during the conversation.
- **`vision`** (fallback) – the decision is computed from the user's facial emotion and the novelty of the scene.

---

## Storage Policies

### `pad_arousal` (default) – `PADArousalMemoryModule`

The interaction layer publishes `nadine/affect/state` after every affective appraisal with Nadine's current emotion `label`, PAD `arousal`, and `intensity`. Perception keeps the latest values and uses them when the memorability check runs.

**Memorability**

\[
\text{memorability} = \text{base}(\text{label}) \times \text{intensity}
\]

where `base` is the `MEMORABILITY_AROUSAL_BASE` table in `selective_memory.py`. All emotions have a positive base value, so the score measures activation rather than valence:

| Emotion label | Base |
|---|---|
| anger / angry | 0.85 |
| fear / fearful | 0.80 |
| surprise / surprised | 0.75 |
| joy / happy | 0.60 |
| disgust / disgusted | 0.55 |
| sadness / sad | 0.40 |
| goodbye | 0.30 |
| neutral | 0.10 |
| any other label | 0.10 |

**Decision** (`should_store`)

- If the user has no stored scenes yet (first meeting), the scene is always stored.
- Otherwise the scene is stored when `memorability ≥ arousal_threshold`.
- `main.py` additionally enforces a 15 s cooldown per user between stores.

**Parameters**

- `arousal_threshold` – config.yaml: 0.25 (lowered from 0.40 to capture more everyday moments); code fallback: 0.3.
- `memorability_check_interval` – config.yaml: 3.0 s; code fallback: 2.0 s.

This module loads only CLIP (retrieval embeddings) and Moondream2 (scene descriptions); OpenFace is not needed.

### `vision` (fallback) – `SelectiveMemoryModule`

Kept for comparison. It combines facial emotion salience with scene novelty.

**Emotion analysis**

- [OpenFace 3.0](https://github.com/CMU-MultiComp-Lab/OpenFace-3.0) (`MultitaskPredictor` + `FaceDetector`) with the weights in `perception/weights/`, run on a padded face crop.
- Produces probabilities over `['neutral', 'happy', 'sad', 'surprise', 'fear', 'disgust', 'anger', 'contempt']`.
- `happy_boost_factor` multiplies the `happy` probability and rescales the others, as a stopgap for OpenFace's under-detection of happiness.

**Emotion salience**

Given a probability \(p_e\) and a per-emotion threshold \(t_e\):

\[
\text{salience}(p_e, t_e) = \max\left(0, \frac{p_e - t_e}{1 - t_e}\right)
\]

The per-emotion thresholds are code defaults in `SelectiveMemoryModule` (not read from config): `neutral` 1.0, `happy` 0.5, `sad` 0.7, `surprise` 0.7, `anger` 0.7, `contempt` 0.7, `fear` 0.8, `disgust` 0.8. The final emotion salience is the maximum over the active set `['happy', 'sad', 'surprise', 'fear', 'disgust', 'anger', 'contempt']`; the emotion that produced it is the dominant emotion.

**Novelty**

1. Compute the CLIP embedding of the current frame.
2. Load all previous scene embeddings for the user from `interaction/db/memory/user_profiles/<user_id>/memorable_scenes/embeddings/`.
3. Novelty score = minimum over stored scenes of \(1 - \text{cosine similarity}\); higher means more novel.
4. Novelty salience uses the same threshold mapping with `novelty_threshold`.

**Combined memorability**

\[
\text{memorability} = w_{\text{emotion}} \cdot \text{emotion\_salience} + w_{\text{novelty}} \cdot \text{novelty\_salience}
\]

The scene is stored when `memorability ≥ memorability_threshold`, subject to the same 15 s cooldown.

**Parameters** (config.yaml value, code fallback in parentheses)

- `w_emotion` 0.8 (0.5), `w_novelty` 0.2 (0.5)
- `novelty_threshold` 0.45 (0.3)
- `memorability_threshold` 0.4 (0.5)
- `happy_boost_factor` 1.2 (1.0)

---

## Shared Components

- **Scene embedding (CLIP)** – `openai/clip-vit-base-patch32` embeds the full RGB frame; embeddings are \(L_2\)-normalized for cosine comparisons. The interaction layer uses the same model for visual-memory retrieval.
- **Scene description (VLM)** – `vikhyatk/moondream2`, pinned to revision `2025-06-21`, generates a one-sentence caption for each stored scene. If the model fails to load, storage proceeds without a description.
- All models are loaded once at initialization on the best available device (`cuda:0`, then MPS, then CPU). Ollama fills GPU 1 first, so perception models take GPU 0.

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
  - JSON files, filename `scene_YYYYMMDD_HHMMSS_metadata.json`. Common fields: `scene_id`, `timestamp`, `image_path`, `memorability`, `description`.
  - Under `pad_arousal`: `emotion_label`, `intensity`, and a human-readable `reason` string.
  - Under `vision`: `emotion_salience`, `novelty_salience`, and the full `emotion_probs` distribution.

This structure lets the interaction layer's memory retrieval agent discover and rank scenes for a user.

---

## Configuration Hooks

Tune selective memory via the `selective_memory` block of `perception/config.yaml`:

- `policy` – `"pad_arousal"` (default) or `"vision"`.
- `arousal_threshold` – `pad_arousal` store threshold (0.25).
- `w_emotion`, `w_novelty`, `novelty_threshold`, `memorability_threshold`, `happy_boost_factor` – `vision` policy parameters.
- `memorability_check_interval` – seconds between checks per user (3.0).

Constants that require a code change:

- `SCENE_STORE_COOLDOWN` (15 s) and `FACE_STORE_COOLDOWN` (10 s) in `main.py`.
- `MEMORABILITY_AROUSAL_BASE` and the per-emotion thresholds in `selective_memory.py`.

!!! note "Differences in the Hybrid Cloud version (nadine_phd)"
    - The default policy is renamed `intensity` (`IntensityMemoryModule`, `intensity_threshold: 0.5`); `pad_arousal` is accepted as a legacy alias.
    - Storage is event-driven by default: one evaluation per dialogue turn when a new `nadine/affect/state` arrives (`NADINE_STORAGE_TRIGGER=event`), instead of the frame-loop interval and cooldown (`interval`).
    - The affect message also carries the user's expressed emotion (`user_label`, `user_intensity`), the user's utterance (`user_message`, stamped onto the scene so it can be retrieved by what was said), and a `suppress_storage` flag for recall turns. `NADINE_STORAGE_EMOTION_SOURCE` selects `user` (default) or `robot` as the driving signal.
    - `store_first_meeting_scene()` stores a dedicated `scene_type: "first_meeting"` scene on first face registration; other scenes are `"moment"`.
    - `NADINE_ENABLE_VISUAL_MEMORY=0` disables the module entirely (A/B study condition), and `fer_sampler.py` logs continuous facial-emotion samples for offline analysis.
