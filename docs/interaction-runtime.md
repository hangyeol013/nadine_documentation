# Interaction Layer – Runtime & MQTT

This page explains how the interaction layer runs at runtime: from microphone input, through the dialogue manager and multi-agent graph, to MQTT messages that drive speech and animations.

---

## Runtime Entrypoint (`nadine/__main__.py`)

`python -m nadine` launches the interaction stack.

### Initialization

`Nadine.__init__(nomqtt: bool)`:

- Loads environment variables from `interaction/.env`.  
- Creates:
  - `logger` via `LoggersFactory.getLogger()`.
  - `Translation` for multi-language translations.
  - `UI` window (status, user text, agent reply).
  - `STTManager` for microphone + Google STT.
  - `MQTTCommunication` for all interaction-layer MQTT I/O.
  - `DialogueManager` for multi-agent conversation logic.

### Modes

`__main__.py` supports:

- **Default mode**: voice + UI + MQTT.
  - `nadine = Nadine(nomqtt=False)`
  - `nadine.start_all()`
- **`--nomqtt`**:
  - Runs without MQTT (e.g. for offline experimentation).
- **`--chatmode`**:
  - Text-only mode:
    - Creates `DialogueManager()` directly.
    - Simple REPL in the console:
      - User types a message, DM returns text.

---

## Voice Interaction Flow

In normal mode:

1. `Nadine.start_all()`:
   - Starts STT listening.
   - Sets initial UI status (microphone, user availability, etc.).
   - Starts the UI event loop.

2. **User speaks**:
   - `STTManager` converts audio to text and calls `Nadine.user_speech_detected(text)`.

3. **user_speech_detected**:
   - Suspends STT while Nadine is speaking (when MQTT is enabled).
   - Translates user input to English if current `language` is not English.
   - Calls `DialogueManager.processInput(text_en)`.
   - Updates the UI (user input + agent output).
   - Calls `mqtt_comm.speak(reply_en, self.language)` to trigger speech and animation.

4. **After response**:
   - STT is re-activated.
   - UI status is updated again to reflect current listening/speaking state.

This loop repeats for each user utterance.

---

## DialogueManager Runtime (`dm.py`)

`DialogueManager.processInput(user_input: str)` orchestrates the main interaction logic.

### Initialization (`__init__`)

- Creates:
  - `mqtt_comm` – shared `MQTTCommunication` instance.
  - `logger` – shared logger.
  - `chat_history` – list of LangChain `HumanMessage`/`AIMessage`.
  - `user_id` – unique ID via `generate_unique_user_id()`.
  - `user_info` – default profile dict via `user_info_init(user_id)`.
  - `c_state` – current graph state (custom state dict).
  - `multi_agent_graph` – compiled LangGraph from `build_agent_graph()`.
  - `conversation_limit` – how many recent turns to keep in `chat_history`.
- Calls `warmup_llms()` to pre-initialize key LLMs.

### State refresh & name confirmation

Before invoking the graph, DM:

- Checks face-recognition info via `mqtt_comm.get_detected_user_info()`.  
- `_refresh_state(detected_user_id)`:
  - If a different user was detected:
    - Loads their `user_info.json` from the interaction DB.
    - Resets MQTT detection state.
  - Updates `c_state` via `default_custom_state(c_state, chat_history, user_info)`.

If the memory agents previously requested name confirmation, `name_confirmation(user_input)`:

- Handles:
  - Confirming a suggested existing user.  
  - Creating a new user from a name explicitly mentioned by the user.  
  - Rotating through remaining candidate names if needed.  
- Synchronizes user info back to face recognition via MQTT.

### Graph invocation

After state prep:

- `results = multi_agent_graph.invoke(self.c_state)`

The result includes:

- Updated `user_info`
- Updated `affect` state
- Updated memories
- `final_message` – raw response text/JSON
- Optional `name_confirmation` payload
- `intent` – classified intent (e.g., `first_greeting`, `end_conversation`)

The DM:

- Optionally calls `set_language_callback` if `results["language"]` changed.  
- Adopts `self.c_state = results`.  
- Ensures `user_info` and `user_id` in DM align with graph output.  
- Extracts:
  - Final text + emotion via `_extract_robot_response(results)`.  
- Updates `chat_history` with the new AI message.  
- Resets chat history on `end_conversation` and trims to `conversation_limit` messages.

### Motion side-effects

For certain intents (`first_greeting`, `end_conversation`), DM asks the control layer to wave:

- `self.mqtt_comm.give_wave()` → publishes a `nadine/agent/control/animation` command.

---

## MQTT Topics (Interaction Perspective)

The interaction layer uses `MQTTCommunication` as its main MQTT client.

**Subscribed**

- `nadine/graph/user_detected`
  - From perception layer.
  - Payload: `{"user_name": str, "user_id": str, "confidence": float}`.
  - Used to track which user is currently in front of Nadine.

- `nadine/graph/face_stored`
  - From perception layer.
  - Payload: `{"user_name": str, "user_id": str, "status": "face_stored" | "face_stored_new_user"}`.
  - Used to update `interaction/db/user_ids.json` when new users are added.

- `nadine/agent/feedback/start_speak`, `nadine/agent/feedback/end_speak`
  - From control layer.
  - Indicate when Nadine starts/finishes speaking.

**Published**

- `nadine/face_recognition/user_info`
  - To perception layer.
  - Payload: `{"user_name": ..., "user_id": ...}`.
  - Used when memory agents or DM finalize a user’s name → triggers face storage.

- `nadine/perception/capture_current_view`
  - To perception layer.
  - Payload: image path string.
  - Used to request a snapshot for vision/visual memory.

- `nadine/agent/control/speak`
  - To control layer.
  - Payload: final response text (in the appropriate language).
  - Triggers TTS + lip-sync + associated animations.

- `nadine/agent/control/animation`
  - To control layer.
  - Payload: animation name.
  - Used by helper methods like `give_wave`, `give_greeting`, `give_smile`, etc.

---

## Quick Dev Tips

- To debug the LangGraph flow in isolation, run `graph.py` directly (it has a CLI `main()` loop).  
- To test the dialogue manager without STT/UI, run:
  - `python -m nadine --chatmode`  
- Use the **Agents & Graph** and **Memory & RAG** pages to understand how state fields like `user_info`, `conversation_memory`, `episode_memory`, and `visual_memory` are set and used.


