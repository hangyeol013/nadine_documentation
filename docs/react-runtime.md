# ReAct Platform – Runtime, Audio & MQTT

This page describes the processes of `nadine_stable`, the topics they exchange, and the speech path from microphone to lips, including what happens when the user interrupts Nadine.

---

## Processes and Entry Points

| Module | Entry point | What it starts |
|---|---|---|
| Perception | `perception_asd_depth/rs_asd.py` | RealSense pipeline at 640×480 and 30 fps, YOLOv8 face tracking, MQTT publisher, an OpenCV preview window |
| Interaction | `python3 -m nadine` in `interaction_SoR_v2` | Google STT thread, Tkinter UI, MQTT client, dialogue manager |
| Control | `control_StopMic_asd_depth/main.py` | MQTT server, robot controller with its 30 ms motion loop, Azure TTS, serial link on `/dev/ttyUSB0` at 115200 baud with 28 channels |

All three connect to the broker at `localhost:1883` and fall back to the host name `emqx` if that fails.

### Perception loop

Each frame is aligned to the color stream and passed to YOLOv8 tracking with a confidence of 0.7. For each face the depth at the midpoint between the eye keypoints is read, falling back to the box center if the keypoints are missing. The **tracked user** is the face with the tracker ID chosen earlier; it is replaced by the closest face when that face is more than one meter nearer, when the current track has been held for 2.5 s, or when the tracked face is gone. The tracked face's eye point is deprojected to 3D meters and published to `nadine/agent/control/look_at` unless it is exactly the origin. Pressing `q` in the preview window stops the process.

### Interaction startup

`Nadine.__init__` loads `.env`, creates the translation client, the UI, the STT manager, the MQTT client, and the dialogue manager, and wires the UI's gaze buttons to the MQTT client. `start_all()` starts the STT thread, activates the microphone, and enters the Tkinter main loop. The session language starts as English.

---

## MQTT Topics

| Topic | Publisher → Subscriber | Payload | Purpose |
|---|---|---|---|
| `nadine/agent/control/look_at` | Perception → Control (also relayed by Interaction from `nadine/user/position`) | JSON `{x, y, z}` in meters | Face tracking gaze target |
| `nadine/agent/control/look_at_target` | Interaction UI → Control | Posture name: `Posture_LookAtInterviewer`, `Posture_LookAtZoom`, `LOOKUPPostureDefault` | Fixed gaze direction, see below |
| `nadine/agent/control/speak` | Interaction → Control | JSON `{"text", "locale"}`; a plain string is accepted and read as `en-US` | Synthesize and speak |
| `nadine/agent/control/animation` | Interaction → Control | XML `animation_name`, for example `smile`, `shake`, `LOOKUP_Waving`, the two `Receptionist_Greeting_*_NoSmile` gestures | Play a gesture |
| `nadine/agent/control/sing` | Interaction → Control | Relative song path such as `en/twinkle_twinkle_hanami` | Play a library song |
| `nadine/agent/control/sing_data` | Interaction → Control | gzip-compressed WAV bytes | Play a made-up song rendered by the interaction process, so playback works when control runs elsewhere |
| `nadine/agent/feedback/start_speak` | Control → Interaction | `start_speak` | Nadine started producing audio |
| `nadine/agent/feedback/end_speak` | Control → Interaction | `end_speak` | Nadine finished producing audio |
| `nadine/user/name`, `nadine/user/emotion`, `nadine/user/position`, `nadine/user/speech` | External → Interaction | Name, emotion label, position JSON, transcript | Handled by the interaction layer but published by nothing in this repository |

Control subscribes to `nadine/agent/control/#` and handles `sing_data` before decoding, because its payload is binary.

---

## The Speech Path

### Speech recognition

`GoogleSTT` runs in its own thread and streams the microphone to Google Cloud Speech v2 with the `latest_short` model, interim results, voice-activity events, automatic punctuation, word confidence, and a phrase set that boosts "Nadine", "Nadia Thalmann", and "Heinz Nixdorf MuseumsForum". The language code is the session language's Google tag.

- Audio is 16 kHz mono in 100 ms buffers. The generator joins every buffer queued since the last send and emits the result in slices of at most 25600 bytes, the largest message the streaming API accepts. Without the slicing, any stall longer than 800 ms produced an oversized message and the service closed the stream with an error.
- An interim transcript with confidence above 0.6 is kept as a candidate. On a final result the final text is used, or the candidate if the final text is empty, and the callback in `Nadine` runs the turn.
- The recognizer has four states: `ACTIVE`, `SUSPENDED`, `UPDATE_LANGUAGE`, and `EXIT`. Suspending closes the microphone stream, which ends the current request; activating opens a new stream and request. A language change while suspended takes effect on the next activation.

### Muting while Nadine speaks

The microphone is closed whenever Nadine produces audio, which is what `StopMic` in the module name refers to. Two mechanisms overlap:

1. `user_speech_detected` suspends STT before calling the dialogue manager and reactivates it in a `finally` block after the reply has been published.
2. Control publishes `start_speak` when synthesis begins and `end_speak` when the lip channels go idle or a song ends. The interaction layer suspends STT on the first and activates it on the second. Songs are bracketed the same way, so Nadine does not transcribe her own singing.

### Synthesis and lip-sync

Control's `make_nadine_speak` resets to `LOOKUPPostureDefault` unless the gaze is locked, starts `AzureTTS.processString(text, locale)` in a thread, and publishes `start_speak`. The utterance is sent as SSML: voice `en-US-JennyMultilingualV2Neural`, rate −10%, style `whisper`, viseme type `redlips_front`, and the text wrapped in a `<lang xml:lang="...">` element so the multilingual voice speaks the requested locale rather than guessing it. Two Google tags are mapped to Azure locales, Mandarin to `zh-CN` and Cantonese to `zh-HK`; the text is XML-escaped so `&` or `<` cannot break the request.

Viseme events arriving during playback are mapped to three lip motor values and applied to channels 4 to 6 on every frame of the motion loop. Visemes from a superseded request are discarded by a request counter.

### Barge-in

When a new transcript arrives while Nadine is still speaking, the interaction layer publishes a new `speak` message. In control:

1. `processString` increments the request counter. If an utterance is currently inside `speak_ssml`, it calls `stop_speaking_async()` on that synthesizer, which makes the running call return as canceled by the user and release the synthesis lock. Stopping is skipped when nothing is playing, because stopping an idle synthesizer makes its next request time out and produced a silent lip pass before the audio.
2. Under the synthesis lock, the new utterance checks that it is still the newest request, creates a fresh `SpeechSynthesizer`, and speaks. Synthesizers are created per utterance and only under the lock, after the previous one has fully returned; an earlier design that recreated the synthesizer from a second thread left an orphaned instance holding the audio device, which produced lip movement with no sound after an interruption.
3. A canceled result caused by an error, rather than by a barge-in, is retried once with a new synthesizer after 0.6 s.

The synthesizer's output is an `AudioOutputConfig` on the ALSA `pulse` device rather than the default speaker. With the default device, a stop in mid-playback leaked the hardware handle inside the SDK, the sound card stayed locked, PulseAudio's sink suspended, and every later utterance was silent until restart. As a PulseAudio client the stop only abandons a daemon-side stream. This also makes the SDK honor `PULSE_SINK`, which the Zoom mode relies on.

Before a song plays, `release_audio_device()` drops the synthesizer and speaker config so PulseAudio can claim the card for `paplay`; the next utterance simply creates a new synthesizer.

---

## Gaze Control

Perception's look-at messages drive `look_at_position`, which computes neck and eye angles from the 3D point. Two other inputs override it:

- **Fixed gaze postures.** The UI's "Look at Interviewer" and "Look at Zoom Screen" buttons publish `look_at_target`; control applies the posture and sets `gaze_locked`. While locked, face tracking is ignored, speaking does not reset the posture, gestures return to the locked posture instead of the default, and the periodic blink uses the eyelid-only `blink` animation instead of `LOOKUPPostureDefaultBlink`, which would re-apply the default head pose. "Default Posture" publishes `LOOKUPPostureDefault`, which clears the lock and restores tracking.
- **Head gestures.** While a nod or shake plays, look-at is ignored until the head joints are idle.

The face-tracking geometry uses a neck-tilt offset ported from the hybrid-cloud platform.

---

## Zoom Audio Mode

`start_nadine.sh --zoom-audio` supports a hybrid interview in which one interviewer is in the room and another joins on Zoom from the same machine. `scripts/zoom_audio_setup.sh` builds a PulseAudio graph:

1. Loads echo cancellation on the physical microphone and speaker, yielding a cleaned mic source and a speaker sink that doubles as the echo reference.
2. Creates four null sinks: `nadine_tts` (robot voice), `zoom_capture` (what Zoom plays), `to_zoom` (what Zoom hears), and `nadine_mic` (what the robot's STT hears, 16 kHz mono).
3. Wires loopbacks so the robot's voice reaches the room speaker and Zoom; the remote voice reaches the room speaker and the robot; and the in-room interviewer reaches Zoom and the robot. Echo cancellation removes the robot's voice and the remote voice from the room microphone.
4. Remaps `to_zoom.monitor` into a real source named "Nadine Virtual Mic to Zoom", because Zoom on Linux hides plain monitor sources.
5. Sets `nadine_tts` and `nadine_mic.monitor` as defaults and records the loaded module IDs for teardown.

The launcher then starts control with `PULSE_SINK=nadine_tts` and interaction with `PULSE_SOURCE=nadine_mic.monitor`, and sets the microphone gain on the physical mic rather than the virtual default. In Zoom, the speaker is "Zoom Capture (Nadine)" and the microphone is "Nadine Virtual Mic to Zoom"; automatic microphone volume and noise suppression should be turned off.

`scripts/zoom_listen_toggle.sh on|off|toggle|status` mutes or unmutes only the loopback from Zoom into the robot's microphone, so the robot can stop transcribing the remote participants while everyone else keeps hearing everything. The UI's "Robot listens to Zoom remote" checkbox calls this script and shows its result; it reports an error if the routing is not loaded. `scripts/zoom_audio_teardown.sh` unloads the modules and restores the physical devices as defaults.

---

## Console and Shutdown

Control runs a console thread in its terminal: `s`, `ger`, or `f` prompt for text to speak; `g` prompts for an animation name; `p` for a posture name; `servo` sets one channel's default position; `shut` plays the shutdown animation and stops motion; `q` exits the console. The interaction UI's language combo box changes the STT language immediately; closing the window is not intercepted, so stop the process from its terminal.
