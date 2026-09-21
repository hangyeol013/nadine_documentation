# Control Layer – Overview

The control layer drives Nadine's **physical embodiment**: head/eye pose, gestures, and speech (audio + lip movements).

If you are new to the project, start with **Project Overview**, then use this page to understand what the control component does and how to run it.

---

## Responsibilities

- **Receive high-level commands** via MQTT from the interaction and perception layers:  
  - `speak`, `look_at`, `look_at_target`, `animation`
- **Execute joint-level motion** using XML animation files and per-joint trajectories
- **Generate speech audio and lip movements** with [Azure Text-to-Speech](https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech); the lips are driven live from Azure viseme events
- **Send feedback events** (start/end speaking) back to the interaction layer

---

## Files and Modules

Main files under `control/`:

- **`main.py`** – entrypoint; loads `control/.env` and `config.yaml`, parses CLI arguments, and starts `NadineServer`.
- **`config.yaml`** – animation XML path, TTS provider, and legacy voice-path keys.
- **`checker.ini`** – motion-controller profile: serial port, channel count, and one line per channel with name, default, min, and max.
- **`run.sh`** – convenience script to activate the `nadine_new` env and run `main.py`.

Key modules in `nadine/control/`:

- **`NadineServer.py`** – owns the MQTT client, subscribes to control topics, and dispatches messages to `AgentControlHandler`.
- **`AgentControlHandler.py`** – thin adapter that maps commands (`lookAtPosition`, `lookAtTarget`, `speak`, `touchTarget`) to `NadineControl` methods.
- **`NadineControl.py`** – core robot controller; loads the animation library, initializes joints, runs the 30 ms motion loop, and coordinates TTS and lip-sync.
- **`Animations.py`** – `AnimationLibrary` for loading animation sequences from XML.
- **`AzureTTS.py`** – Azure Text-to-Speech integration; receives viseme events and updates the lip channels.
- **`LipAnimationGenerator.py`** – lookup table from Azure viseme IDs (0–21) to the three lip motor values.
- **`Joint.py`** – simple joint model for servo trajectories.
- **`SerialComm.py`**, **`Checker.py`**, **`StructDef.py`** – low-level serial protocol with Nadine's motion controller.
- **`XMLAnimations/`** – XML animation scenes defining gestures and postures.

Animations are addressed by the `<animation_name>` element inside each XML file, not by the file name. For example, `LOOKUP_PostureDefault.xml` defines the animation `LOOKUPPostureDefault`.

---

## How to Run

### Prerequisites

- **Environment**: `nadine_new` conda environment (from `control/environment.yml`).  
- **Hardware**:
  - Nadine's motion controller on the serial port named in `checker.ini` (`/dev/ttyUSB0`, 115200 baud, 28 channels). The port is opened as soon as `NadineControl` initializes, so startup fails without it.
  - Speakers connected to the control machine.  
- **Services**: MQTT broker at `localhost` or `emqx`.  
- **Credentials**: `control/.env` with `AZURE_SERVICE_KEY` and `AZURE_SERVICE_REGION` (see **TTS settings** in Runtime & MQTT).
- **Paths**:
  - `control/config.yaml` sets the animation XML directory.

### Start command

From the control directory:

```bash
cd /home/miralab/Development/nadine_local/control
conda activate nadine_new
./run.sh
```

or:

```bash
cd /home/miralab/Development/nadine_local/control
conda activate nadine_new
python3 main.py
```

`start_nadine.sh` at the project root starts control as its last step. You can override the animation directory on the command line:

```bash
python3 main.py -animationXMLPath XMLAnimations
```

`main.py` also accepts `-voicepath`, `-voicepathGerman`, and `-voicepathFrench`. These are legacy options: the values are stored on `NadineServer` and never read, because speech comes from Azure TTS rather than local voice files.

---

## Configuration (`control/config.yaml`)

Control-layer configuration lives under the `control:` key:

- **`animations`**
  - `animation_xml_path` – directory containing animation XML files (relative to `control/` or absolute). Defaults to `XMLAnimations`.

- **`tts`**
  - `provider` – `"azure"`. The only provider implemented; voice, rate, and style are set in `AzureTTS.py`.

- **`voice`**
  - `default_path`, `german_path`, `french_path` – legacy voice-file paths, empty by default and unused.

`main.py` loads this via `load_control_config()` and passes the animation XML path to `NadineServer` → `AgentControlHandler` → `NadineControl.load_animation_library(...)`.

---

## Where to Go Next

- See **Control Layer / Runtime & MQTT** for details on how MQTT commands are turned into motions and speech.  
- Use the **Project Overview** page for how control interacts with the other layers.
