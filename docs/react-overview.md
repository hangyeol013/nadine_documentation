# ReAct Platform – Overview & Architecture

This section documents the **ReAct, Cloud** version of Nadine (`nadine_stable`), the platform used for public demonstrations and recorded sessions. It runs the same three-layer MQTT stack as the multi-agent platform but with a different interaction layer and older, leaner perception and control modules. For how it relates to the other versions, see [Platforms](platforms.md).

The three pages that follow cover the [dialogue manager and tools](react-agent.md), the [runtime, audio path, and MQTT topics](react-runtime.md), and the [singing pipeline](react-singing.md).

---

## Purpose

The platform is built for sessions where robustness matters more than the memory model: a fixed set of capabilities, cloud language models, and an audio path that survives interruption. Everything the dialogue manager can do is a tool it can select; adding a capability means adding a tool.

---

## Repository Layout

```
nadine_stable/
├── compose.yaml                   # EMQX MQTT broker
├── start_nadine.sh                # Launcher: audio setup, broker, three module tabs
├── requirements.txt               # Pinned packages for the nadine_mqtt conda env
├── scripts/
│   ├── zoom_audio_setup.sh        # PulseAudio routing for hybrid Zoom interviews
│   ├── zoom_audio_teardown.sh
│   └── zoom_listen_toggle.sh      # Mute/unmute the remote Zoom feed into STT
├── perception_asd_depth/
│   ├── rs_asd.py                  # RealSense + YOLOv8 face tracking, publishes look_at
│   ├── models/                    # yolov8n-face.pt
│   └── run.sh
├── interaction_SoR_v2/
│   ├── nadine/
│   │   ├── __main__.py            # Entry point: STT, UI, MQTT, dialogue manager
│   │   ├── dm/                    # ReAct agent, prompt, tools, memory, RAG, singing
│   │   ├── stt/                   # Google Cloud Speech streaming
│   │   ├── communication/         # Perception state bridge
│   │   ├── common/                # MQTT client, languages, translation, logging
│   │   └── ui/                    # Tkinter monitor window
│   ├── data/                      # ChromaDB stores: knowledge/, memory/
│   ├── rag_files/                 # Nadine_Platform.pdf for the knowledge base
│   └── run.sh
├── control_StopMic_asd_depth/
│   ├── main.py                    # Entry point
│   ├── nadine/control/            # MQTT server, robot controller, Azure TTS, serial
│   ├── XMLAnimations/             # Animation and posture XML files
│   ├── songs/                     # Pre-rendered songs: en/, fr/, makeup/
│   ├── checker.ini                # Serial port and 28-channel table
│   └── run.sh
└── singing_pipeline/              # Offline tooling: DiffSinger renderer, RVC, datasets
```

The directory names carry their history: `SoR_v2` is the second version of the SoR-ReAct (Social Robotics ReAct) interaction design, `asd_depth` refers to depth-based active-speaker selection in perception, and `StopMic` refers to muting the microphone while Nadine speaks.

---

## How the Layers Map to the Shared Stack

The MQTT topics, the Azure TTS voice, the XML animation format, and the serial protocol are the same as in the multi-agent platform, so the [Control](control-overview.md) and [Perception](perception-overview.md) sections apply to the mechanisms. The modules themselves differ:

| Layer | `nadine_stable` | Multi-agent platform (`nadine_local`) |
|---|---|---|
| Perception | One script, `rs_asd.py`: YOLOv8 face detection with tracking, closest-face selection by depth, and 3D eye position published to `nadine/agent/control/look_at`. No face recognition, no emotion detection, no selective memory. | Face recognition with InsightFace, user profiles, emotion analysis, selective visual memory, several topics. |
| Interaction | Retrieval-augmented ReAct agent with a fixed tool set; per-user conversation memory and a knowledge base in ChromaDB; Google STT; Tkinter UI with gaze and Zoom controls. | LangGraph multi-agent graph with fine-tuned local models, PAD affect, visual memory. |
| Control | Same module set plus singing playback, gaze locking for interviewer and Zoom postures, per-utterance Azure synthesizer serialized by a lock, PulseAudio-routed playback. Speak payloads are JSON with a locale. | Plain-text speak payloads; no singing; gaze target latch without the interviewer and Zoom lock. |

Two consequences of the perception module follow directly from the code:

- Nothing in this repository publishes `nadine/user/name`, `nadine/user/emotion`, or `nadine/user/speech`. The interaction layer subscribes to them and has handlers, but in this build the user ID stays `unknown` and the user emotion stays `neutral` unless an external publisher provides them. Because long-term memory is stored and retrieved only for identified users, it is inactive without such a publisher.
- The look-at position bypasses the interaction layer: perception publishes straight to the control topic.

---

## Environments and Credentials

All three modules run in one conda environment, `nadine_mqtt`, activated by each module's `run.sh`. `requirements.txt` at the repository root pins the packages.

Two `.env` files hold credentials and are never committed:

- `interaction_SoR_v2/.env`: `GOOGLE_APPLICATION_CREDENTIALS` (path to the service-account JSON used for Speech-to-Text and Translation), `GOOGLE_CLOUD_PROJECT`, `OPENAI_API_KEY`, `SERPER_API_KEY` (web search and news), `LANGCHAIN_API_KEY` (optional tracing). `OPENWEATHERMAP_API_KEY` enables the weather tool if present.
- `control_StopMic_asd_depth/.env`: `AZURE_SERVICE_KEY`, `AZURE_SERVICE_REGION`.

The interaction module also reads the control module's `.env` when it needs Azure credentials for song rendering. `OPENAI_API_KEY` is required: the agent, the contextualizer, and both ChromaDB stores use OpenAI models and embeddings.

The knowledge base is built on first start from the `Nadine Social Robot` Wikipedia article and `rag_files/Nadine_Platform.pdf`, split into 1000-character chunks with 200 overlap, and persisted under `data/knowledge/`. Delete that folder to rebuild it.

---

## Starting the Platform

```bash
cd nadine_stable
./start_nadine.sh [--mic-volume=<0-150>] [--zoom-audio]
```

The launcher:

1. Configures audio. By default it reloads PulseAudio echo cancellation on the default devices and sets the microphone gain (default 20%). With `--zoom-audio` it instead runs `scripts/zoom_audio_setup.sh` and pins TTS to the `nadine_tts` sink and STT to the `nadine_mic.monitor` source (see [Runtime, Audio & MQTT](react-runtime.md)).
2. Restarts the EMQX broker with `docker compose up -d`. The two data volumes are declared external and must exist.
3. Makes `/dev/ttyUSB0` writable and opens three `gnome-terminal` tabs: control, interaction, perception, each running its `run.sh`.

Each module can also be started alone from its own directory with `./run.sh`. The interaction module accepts `--nomqtt` (no broker, user always present) and `--chatmode` (text REPL against the dialogue manager, no STT or UI).

The interaction layer's `run.sh` filters known ALSA and JACK probe messages from stderr so real errors stay visible.
