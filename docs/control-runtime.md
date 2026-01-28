# Control Layer – Runtime & MQTT

This page explains how the control server processes MQTT commands and turns them into robot motions and speech.

---

## Entrypoint (`main.py`)

`main.py` is responsible for:

- Loading environment variables from `control/.env` (Azure TTS, etc.).  
- Loading `control/config.yaml` via `load_control_config()`.  
- Parsing optional CLI arguments:
  - `-voicepath`, `-voicepathGerman`, `-voicepathFrench`, `-animationXMLPath`.  
- Creating a `NadineServer` instance with the resolved voice paths.  
- Setting the animation XML path on the server.  
- Calling `start_server()` to begin handling MQTT commands.

Once started, the process runs until you stop it (CTRL+C).

---

## MQTT Server (`NadineServer`)

`NadineServer` owns the MQTT client and bridges topics to robot actions.

### Setup

- Creates a `paho.mqtt.client.Client`.  
- Registers:
  - `on_connect` – called when the client connects.  
  - `on_message` – called when messages are received.  
- Attempts to connect to an MQTT broker:
  - First `localhost:1883`, then falls back to `emqx:1883`.

### Subscriptions

On connect, the server subscribes to:

- `nadine/agent/control/#`

This wildcard covers:

- `nadine/agent/control/speak`  
- `nadine/agent/control/look_at`  
- `nadine/agent/control/animation`

### AgentControlHandler creation

When `start_server()` is called:

- Logs that the MQTT handler is starting.  
- Creates `AgentControlHandler(animation_xml_path)`.  
- Attaches itself to the robot:
  - `agentcontrol_handler.robot.nadine_server = self`

This allows `NadineControl` to send feedback (`start_speak`, `end_speak`) back through the server.

### Message handling

In `on_message`, the server routes topics to `AgentControlHandler`:

- **`nadine/agent/control/look_at`**
  - Payload: JSON `{"x": float, "y": float, "z": float}`.
  - Action: `agentcontrol_handler.lookAtPosition(...)` → `NadineControl.look_at_position(...)`.

- **`nadine/agent/control/speak`**
  - Payload: plain text string.
  - Action: `agentcontrol_handler.speak(text, volume=0)` → `NadineControl.make_nadine_speak(...)`.

- **`nadine/agent/control/animation`**
  - Payload: string/enum for a predefined animation.
  - Action: forwarded to animation handling (e.g. `playAnimation` / `touchTarget` depending on implementation).

### Feedback topics

`NadineServer` also exposes:

- `speakBegin()` → publishes `nadine/agent/feedback/start_speak`  
- `speakEnd()` → publishes `nadine/agent/feedback/end_speak`

These are called from `NadineControl` at the start and end of speaking to synchronize with the interaction layer and UI.

---

## High-Level Control (`AgentControlHandler`)

`AgentControlHandler` wraps `NadineControl` to present a simple API to the rest of the system.

### Initialization

In `__init__(animation_xml_path)`:

- Creates `self.robot = NadineControl()`.  
- Calls `self.robot.load_animation_library(animation_xml_path)`.  
- Calls `self.robot.init_me()`:
  - Initializes joints and default posture.
  - Starts idle movement (blinking) threads.
  - Sets up Azure TTS and checker.

### Key methods

- **`lookAtPosition(position)`**
  - Expects a dict with `{"x", "y", "z"}`.  
  - Calls `self.robot.look_at_position(...)` to orient head/eyes.

- **`lookAtTarget(target)` / `endLookAt()`**
  - Starts/stops continuous look‑at behavior for a named target.

- **`speak(phrase, volume)`**
  - Calls `self.robot.make_nadine_speak(phrase, volume)`.  
  - `NadineControl` then:
    - Ensures a suitable posture.
    - Uses Azure TTS to generate audio and lip/jaw trajectories.
    - Updates mouth‑related joints and triggers feedback via `nadine_server.speakBegin()/speakEnd()`.

- **`playAnimation(animation)`**
  - Maps a logical animation identifier (e.g. `WHY`, `WAVE_HAND`, `NOD_YES`) to an XML animation name.
  - Calls `self.robot.play_animation("SomeAnimationName")`.

Other methods (point/greet/move) are stubs or thin wrappers and can be extended as needed.

---

## Core Robot Controller (`NadineControl`)

`NadineControl` is responsible for turning high‑level requests into joint‑level trajectories and serial commands.

### Initialization (`init_me`)

Typical steps:

- Create 28 `Joint` objects (for Nadine’s servos) with default positions.  
- Initialize the body configuration and idle state.  
- Create a `Checker` instance (drives playback and safety checks).  
- Create `AzureTTS` bound to the checker.  
- Start:
  - A **blink/idle movement thread** (`endless_movements`).  
  - A **console input thread** (`ask_for_text`) for debugging.  
  - A **look‑at target thread** to maintain gaze when a target is set.

### Look-at behavior

Methods like `look_at_position(...)`, `look_at_target(...)`, and `end_look_at()`:

- Compute joint trajectories for head/eye servos based on a 3D position or named target.  
- Update associated `Joint` trajectories so that the checker loop sends appropriate serial commands.

### Speech and lip-sync (`make_nadine_speak`)

When `make_nadine_speak(text, volume)` is called:

- Ensure Nadine is in a speaking posture (e.g. `"LOOKUPPostureDefault"`).  
- Log the speech request.  
- Use `AzureTTS` to:
  - Generate speech audio.
  - Compute lip/jaw trajectories (`channel5`, `channel6`, `channel7`, etc.).  
- Clear and repopulate mouth-related joints with the new trajectories.  
- Set flags indicating that speech is in progress and call:
  - `nadine_server.speakBegin()` at start.  
  - `nadine_server.speakEnd()` when speech completes.

### Animation execution

For named animations:

- `NadineControl` uses `AnimationLibrary` to retrieve per‑joint sequences for the given animation.  
- Populates each relevant `Joint`’s trajectory.  
- A background loop (inside `Checker`) steps through frames, sending servo positions over `SerialComm`.

---

## MQTT Topics (Control Summary)

**Subscribed (Control consumes)**

- `nadine/agent/control/speak`  
  - Payload: `"<text to speak>"`  
  - Effect: triggers TTS + lip‑sync and potentially an associated animation.

- `nadine/agent/control/look_at`  
  - Payload: `{"x": float, "y": float, "z": float}`  
  - Effect: orients Nadine’s head/eyes to look at the given 3D position.

- `nadine/agent/control/animation`  
  - Payload: string/enum identifier  
  - Effect: plays a predefined gesture/posture animation.

**Published (Control produces)**

- `nadine/agent/feedback/start_speak`  
  - Emitted when Nadine starts speaking.

- `nadine/agent/feedback/end_speak`  
  - Emitted when Nadine finishes speaking.

These topics close the loop between perception (gaze), interaction (dialogue), and control (motion and speech).

---

## Extension Points

Common places to extend the control layer:

- **Add new animations**
  - Create a new XML file in `XMLAnimations/`.  
  - Add a case in `AgentControlHandler.playAnimation(...)` mapping an enum/name to your XML animation.

- **Change idle behavior or default posture**
  - Modify `NadineControl.init_me()` and/or `endless_movements`.

- **Swap TTS provider**
  - Implement a new TTS class and replace `AzureTTS` usage in `NadineControl`, making sure lip animation data still drives the same joints.

- **Adapt to different hardware**
  - Update `SerialComm` and `Checker` configurations to match your controller’s serial port and protocol.


