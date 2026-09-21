# Control Layer – Runtime & MQTT

This page explains how the control server processes MQTT commands and turns them into robot motions and speech.

---

## Entrypoint (`main.py`)

`main.py` is responsible for:

- Loading environment variables from `control/.env` (Azure TTS credentials).  
- Loading `control/config.yaml` via `load_control_config()`.  
- Parsing optional CLI arguments:
  - `-animationXMLPath` (used) and `-voicepath`, `-voicepathGerman`, `-voicepathFrench` (legacy, stored but never read).  
- Creating a `NadineServer` instance.  
- Setting the animation XML path on the server (default `XMLAnimations`).  
- Calling `start_server()` to begin handling MQTT commands.

Once started, the process runs until you stop it (CTRL+C or the `q` console command).

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
- Calls `loop_start()`, so MQTT callbacks run in their own thread, concurrently with the 30 ms motion loop described below.

### Subscriptions

On connect, the server subscribes to:

- `nadine/agent/control/#`

This wildcard covers:

- `nadine/agent/control/speak`  
- `nadine/agent/control/look_at`  
- `nadine/agent/control/look_at_target`  
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
  - Published by the perception layer with the tracked user's 3D position.
  - Payload: JSON `{"x": float, "y": float, "z": float}`.
  - Action: `agentcontrol_handler.lookAtPosition(...)` → `NadineControl.look_at_position(...)`.

- **`nadine/agent/control/look_at_target`**
  - Published by the interaction UI's gaze-direction control (`Posture_LookAtInterviewer`, `Posture_LookAtZoom`, `LOOKUPPostureDefault`).
  - Payload: an XML `<animation_name>` of a posture.
  - Action: `agentcontrol_handler.lookAtTarget(...)` → `NadineControl.look_at_target(...)`. Sending `LOOKUPPostureDefault` clears the target.

- **`nadine/agent/control/speak`**
  - Payload: plain text string.
  - Action: `agentcontrol_handler.speak(text, volume=0)` → `NadineControl.make_nadine_speak(...)`.

- **`nadine/agent/control/animation`**
  - Payload: an XML `<animation_name>` string (for example `LOOKUP_Waving`, `shakehand_TwoArgGesture`, `nod`, `shake`).
  - Action: `agentcontrol_handler.touchTarget(payload)` → `NadineControl.play_animation(payload)`. The payload is passed straight through; an unknown name is logged as an error and ignored.

### Feedback topics

`NadineServer` also exposes:

- `speakBegin()` → publishes `nadine/agent/feedback/start_speak`  
- `speakEnd()` → publishes `nadine/agent/feedback/end_speak`

`NadineControl` calls these to synchronize with the interaction layer and UI. See **Speech and lip-sync** below for when exactly they fire.

---

## High-Level Control (`AgentControlHandler`)

`AgentControlHandler` wraps `NadineControl` to present a simple API to the rest of the system.

### Initialization

In `__init__(animation_xml_path)`:

- Creates `self.robot = NadineControl()`.  
- Calls `self.robot.load_animation_library(animation_xml_path)`.  
- Calls `self.robot.init_me()`:
  - Initializes the 28 joints and the default posture.
  - Creates the `Checker`, which reads `checker.ini` and opens the serial port immediately.
  - Creates `AzureTTS` bound to the checker, which starts a background warm-up request to Azure to shorten the first utterance's latency.
  - Starts the motion loop and console threads.

### Key methods

- **`lookAtPosition(position)`**
  - Expects a dict with `{"x", "y", "z"}`.  
  - Calls `self.robot.look_at_position(...)` to orient head/eyes.

- **`lookAtTarget(target)` / `endLookAt()`**
  - Sets or clears a named gaze posture (see **Look-at behavior**). `endLookAt()` is not reachable over MQTT; the target is cleared by sending `LOOKUPPostureDefault`.

- **`speak(phrase, volume)`**
  - Calls `self.robot.make_nadine_speak(phrase, volume)`. The `volume` argument is not used.

- **`touchTarget(animation_name)`**
  - Calls `self.robot.play_animation(animation_name)`. This is the path used by the `animation` topic.

The class also defines `playAnimation` and `setFaceExpression`, which compare against `Animation` and `Facial_Expression` enums that are never imported; they would fail if called and nothing calls them. The remaining methods (point, greet, move, sit, grasp) are stubs.

---

## Core Robot Controller (`NadineControl`)

`NadineControl` turns high-level requests into joint-level trajectories and serial commands.

### Initialization (`init_me`)

- Create 28 `Joint` objects (for Nadine's servos) with default positions and apply the `LOOKUPPostureDefault` posture.  
- Create a `Checker("checker.ini")`, which opens the serial port.  
- Create `AzureTTS` bound to the checker.  
- Start:
  - The **motion loop thread** (`endless_movements`).  
  - A **console input thread** (`ask_for_text`) for debugging.

### Motion loop (`endless_movements`)

Every 30 ms, `endless_movements` calls `group_animations()`, which:

- Reads the next frame value from each of the 28 joints.  
- Drops forbidden lip combinations (both width channels active) and closes the mouth instead.  
- Passes the frame to `Checker.move_one_frame()`, which overrides channels 4–6 with the latest viseme lip values, clamps every channel to its `checker.ini` range, and writes the packet over serial.  
- Triggers a blink whenever the eyelid joint is idle.

Every 8 s, when all joints are idle, the loop also plays a full blink: `blink` while a gaze target is set, otherwise `LOOKUPPostureDefaultBlink`, which returns the body to the default posture.

### Look-at behavior

- `look_at_position(x, y, z)` computes head and eye trajectories toward a 3D point. It is ignored while the robot is shutting down, while a `nod` or `shake` animation is running, or while a gaze target is set.
- `look_at_target(name)` plays the named posture once and latches `look_at_target_name` (cleared when the name is `LOOKUPPostureDefault`). While latched, `look_at_position` is suppressed, `make_nadine_speak` does not reset the posture, and the periodic blink uses the plain `blink` animation instead of the full-posture one. There is no background thread; the posture is set once and held by the joints' default positions.
- `end_look_at()` clears the latch and restores the default head and eye positions.

### Speech and lip-sync (`make_nadine_speak`)

When `make_nadine_speak(text, volume)` is called:

- If no gaze target is set and the body is not already in `LOOKUPPostureDefault`, change to that posture.  
- Log the speech request.  
- Start `AzureTTS.processString(text)` in a background thread. Azure plays the audio on the default speaker and delivers **viseme events** while it plays; each event is mapped by `LipAnimationGenerator.viseme_to_lip()` to three lip motor values and passed to `Checker.updateLips()`. The motion loop applies those values to channels 4–6 on every frame, so the lips follow the audio live.  
- Set the `speak` flag and call `nadine_server.speakBegin()` immediately, before synthesis has produced audio.

The `channel5`/`channel6`/`channel7` trajectory lists that `make_nadine_speak` copies into joints 4–6 are vestiges of an earlier offline lip-sync path; they stay empty because `generate_animation()` is never called.

`speakEnd()` fires in two situations, not at the end of the audio:

- In `group_animations`, when joints 4–6 are idle while the `speak` flag is set. Because the vestigial trajectories are empty, this happens shortly after `speakBegin()`, so `end_speak` can precede the end of the spoken audio.
- In `play_animation`, when a new animation touches channels 4–6 while `speak` is set; the lip trajectories are cleared first.

### TTS settings

`AzureTTS` reads `AZURE_SERVICE_KEY` and `AZURE_SERVICE_REGION` from the environment (`control/.env`, loaded by `main.py`). Each utterance is sent as SSML with:

- voice `en-US-JennyMultilingualV2Neural` (one multilingual voice for all languages),  
- prosody rate `-10%`,  
- expression style `whisper`, degree 1,  
- viseme type `redlips_front`.

Synthesis requests are serialized with a lock. If Azure times out waiting for the first audio chunk, the synthesizer is recreated and the request retried once. Viseme events from a superseded request are discarded.

### Animation execution (`play_animation`)

- Looks up the name in `AnimationLibrary`; the name must match an XML `<animation_name>`.  
- Except for the blink animations, first resets the body to `LOOKUPPostureDefault`; `LOOKUP_Waving` and `SHUTDOWN_NADINE` also clear all pending trajectories.  
- Marks `nod` and `shake` as head animations, which suppresses `look_at_position` until they finish.  
- Populates each joint used by the animation with its channel trajectory, skipping the head and eye channels if a look-at update happened in the last 2 s.  
- `blink` and `breathingSlow` are added as idle movements rather than one-shot trajectories.

### Console commands

The console thread reads commands from stdin: `s`, `ger`, or `f` prompt for text to speak; `g` prompts for an animation name; `p` prompts for a posture name; `servo` sets one joint's default position; `shut` plays `SHUTDOWN_NADINE` and enters shutdown; `q` exits.

---

## MQTT Topics (Control Summary)

**Subscribed (Control consumes)**

- `nadine/agent/control/speak`  
  - Payload: `"<text to speak>"`  
  - Effect: Azure TTS playback with live viseme lip-sync.

- `nadine/agent/control/look_at`  
  - Payload: `{"x": float, "y": float, "z": float}` (from perception)  
  - Effect: orients Nadine's head/eyes to the given 3D position, unless a gaze target or head animation is active.

- `nadine/agent/control/look_at_target`  
  - Payload: posture `<animation_name>` (`Posture_LookAtInterviewer`, `Posture_LookAtZoom`, or `LOOKUPPostureDefault` to clear)  
  - Effect: holds a fixed gaze posture and suppresses position-based look-at until cleared.

- `nadine/agent/control/animation`  
  - Payload: `<animation_name>` string  
  - Effect: plays that gesture or posture animation.

**Published (Control produces)**

- `nadine/agent/feedback/start_speak`  
  - Emitted when a speak request is accepted, before audio starts.

- `nadine/agent/feedback/end_speak`  
  - Emitted when the lip channels go idle or another animation takes over the mouth; may precede the end of the audio.

These topics close the loop between perception (gaze), interaction (dialogue and gaze direction), and control (motion and speech).

---

## Extension Points

Common places to extend the control layer:

- **Add new animations**
  - Create a new XML file in `XMLAnimations/` with a unique `<animation_name>`. It is loaded at startup and can be played by publishing that name to the `animation` topic; no code change is needed.

- **Change idle behavior or default posture**
  - Modify `NadineControl.init_body()` and/or `endless_movements`.

- **Swap TTS provider**
  - Implement a class with the same interface as `AzureTTS` (`processString`, viseme-driven `Checker.updateLips()` calls) and select it in `NadineControl.init_me()`.

- **Adapt to different hardware**
  - Update `checker.ini` (port, channel count, per-channel ranges) and, if the protocol differs, `SerialComm` and `Checker`.

!!! note "Differences in the Hybrid Cloud version (nadine_phd)"
    The `speak` payload may be JSON `{"text": ..., "locale": ...}` so the TTS pronounces the utterance in the active language; plain text still works and defaults to `en-US`. A new `nadine/agent/control/stop_speak` topic interrupts the current utterance for barge-in.
