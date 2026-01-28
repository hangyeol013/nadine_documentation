# Control Layer – Overview

The control layer drives Nadine’s **physical embodiment**: head/eye pose, gestures, and speech (audio + lip movements).

If you are new to the project, start with **Project Overview**, then use this page to understand what the control component does and how to run it.

---

## Responsibilities

- **Receive high‑level commands** via MQTT from interaction/perception:  
  - speak, look_at, play animation
- **Execute joint‑level motion** using XML animation files and per‑joint trajectories
- **Generate speech audio and lip movements** using [Azure Text-to-Speech](https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech) and a lip animation generator
- **Send feedback events** (start/end speaking) back to the interaction layer

---

## Files and Modules

Main files under `control/`:

- **`main.py`** – entrypoint; loads config, parses CLI arguments, and starts `NadineServer`.
- **`config.yaml`** – default paths for voice data and animation XMLs.
- **`run.sh`** – convenience script to activate the `nadine_new` env and run `main.py`.

Key modules in `nadine/control/`:

- **`NadineServer.py`** – owns the MQTT client, subscribes to control topics, and dispatches messages to `AgentControlHandler`.
- **`AgentControlHandler.py`** – high‑level adapter that maps commands (look_at, speak, playAnimation) to `NadineControl` methods.
- **`NadineControl.py`** – core robot controller; loads animation library, initializes joints, manages idle movements, and coordinates TTS + lip animation.
- **`Animations.py`** – `AnimationLibrary` for loading/querying animation sequences from XML.
- **`AzureTTS.py`** – Azure Text‑to‑Speech integration and lip animation generation.
- **`LipAnimationGenerator.py`** – converts audio/phoneme data into mouth/jaw trajectories.
- **`Joint.py`** – simple joint model for servo trajectories.
- **`SerialComm.py`**, **`Checker.py`**, **`StructDef.py`** – low‑level communication and playback protocol with Nadine’s motion controller.
- **`XMLAnimations/`** – XML animation scenes defining gestures and postures.

---

## How to Run

### Prerequisites

- **Environment**: `nadine_new` conda environment (from `control/environment.yml`).  
- **Hardware**:
  - Nadine’s motion controller connected via serial (port configured in `SerialComm`/`Checker`).
  - Speakers connected to the control machine.  
- **Services**: MQTT broker at `localhost` or `emqx`.  
- **Paths**:
  - `control/config.yaml` defines default voice and animation paths.

### Start command

From the control directory:

```bash
cd /home/miralab/Development/nadine_Jan_2026/control
conda activate nadine_new
./run.sh
```

or:

```bash
cd /home/miralab/Development/nadine_Jan_2026/control
conda activate nadine_new
python3 main.py
```

You can override paths on the command line:

```bash
python3 main.py \
  -voicepath <path_to_default_voice> \
  -voicepathGerman <path_to_german_voice> \
  -voicepathFrench <path_to_french_voice> \
  -animationXMLPath XMLAnimations
```

---

## Configuration (`control/config.yaml`)

Control‑layer configuration lives under the `control:` key:

- **`voice`**
  - `default_path` – default (e.g. English) voice data.
  - `german_path` – German voice data.
  - `french_path` – French voice data.

- **`animations`**
  - `animation_xml_path` – directory containing animation XML files (relative to `control/` or absolute).

`main.py` loads this via `load_control_config()` and passes:

- Voice paths to `NadineServer`  
- Animation XML path to `AgentControlHandler` → `NadineControl.load_animation_library(...)`

---

## Where to Go Next

- See **Control Layer / Runtime & MQTT** for details on how MQTT commands are turned into motions and speech.  
- Use the **Project Overview** page for how control interacts with the other layers.


