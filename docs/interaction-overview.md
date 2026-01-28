# Interaction Layer – Overview

The interaction layer is the **main brain** of Nadine.  
It runs a multi-agent dialogue system (based on [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)) that:

- Listens to the user via speech-to-text (STT)
- Routes requests across specialized LLM agents (search, vision, RAG, memory, affect)
- Maintains user-specific memory and affective state
- Produces responses and sends them to the control layer via MQTT (speech + animation)

If you are new to the project, read this page first, then see the **Runtime & MQTT** and **Agents & Graph** pages for deeper details.

---

## Responsibilities

- **Conversation management**
  - Turn raw speech into clean text.
  - Run a multi-agent graph (intent → memory → affect → tools → response).
  - Keep rolling chat history per user.

- **User modeling & memory**
  - Track user ID, name, and profile data.
  - Store and retrieve episodic and conversation memories.
  - Integrate visual memories (from the perception layer).

- **Reasoning & tools**
  - Use web/knowledge search (search agent).
  - Retrieve from Nadine’s internal knowledge (knowledge RAG agent, backed by ChromaDB).
  - Perform visual reasoning (vision agent).

- **Multi-modal output**
  - Generate natural language responses with an LLM.
  - Coordinate speech and robot animations via MQTT.

---

## Directory Structure (Interaction)

Under `interaction/`:

- **`config.yaml`**
  - LLM profiles (`small_llm`, `big_llm`, `response_llm`, `vision_llm`).
  - Agent → LLM profile mapping.
  - Visual-memory retrieval parameters.

- **`run.sh`**
  - Activates the `nadine` conda env and runs `python3 -m nadine`.
  - Sets up a cleanup hook for Ollama models on exit.

- **`nadine/__main__.py`**
  - Entry point for the interaction layer:
    - Loads env variables from `interaction/.env`.
    - Initializes:
      - `UI`
      - `STTManager`
      - `MQTTCommunication`
      - `DialogueManager` (multi-agent graph wrapper)
    - Provides:
      - Normal mode: full voice + UI + MQTT.
      - `--nomqtt`: run without MQTT.
      - `--chatmode`: text-only REPL using `DialogueManager` directly.

- **`nadine/common/`**
  - `loggers.py` – logging utilities (`LoggersFactory`).
  - `language.py` – language enum and helpers.
  - `translation.py`, `translation_llm.py` – text translation tools.
  - `mqtt_comm.py` – interaction-layer MQTT client and helpers.

- **`nadine/stt/`**
  - `google_stt.py`, `stt.py` – [Google Cloud Speech-to-Text](https://cloud.google.com/speech-to-text) integration and microphone handling.

- **`nadine/ui/`**
  - `ui.py` – Qt/GUI window for monitoring interactions (user text, agent reply, status).

- **`nadine/agents/`**
  - Multi-agent graph and specialized agents (documented in **Agents & Graph** and **Memory & RAG** pages).

---

## High-Level Flow

Normal (voice) mode:

1. **User speaks** → `STTManager` converts audio to text.  
2. `Nadine.user_speech_detected`:
   - Suspends STT while the agent is speaking.
   - Translates non-English input into English (if needed).
   - Calls `DialogueManager.processInput(text_en)`.
3. **DialogueManager**:
   - Appends the user message to chat history.
   - Syncs state with any detected face-recognition user.
   - Runs the LangGraph multi-agent workflow.
   - Produces a final response text (and affect state).
4. UI is updated (user input + agent output).  
5. **MQTTCommunication.speak** sends the English response (translated to target language if needed) over:
   - `nadine/agent/control/speak`
6. After speaking finishes, STT is re-activated to listen for the next utterance.

In **chat mode**, steps are similar but:

- No STT or UI.  
- The loop is a simple input/print REPL calling `DialogueManager.processInput`.

---

## Configuration (`interaction/config.yaml`)

The interaction config binds agents to LLM profiles and tunes visual memory:

- **`interaction.llm`**
  - `small_llm` – e.g., `granite4:350m` (low-cost tasks).
  - `big_llm` – e.g., `mistral-small3.2` for heavier reasoning.
  - `response_llm` – main conversation LLM (typically same as `big_llm`).
  - `vision_llm` – dedicated profile for vision agent.

- **`interaction.agents`**
  - Maps logical agents to one of the above profiles, e.g.:
    - `orchestration_agent` → `big_llm`
    - `search_answer` → `small_llm`
    - `response_agent` → `response_llm`

- **`interaction.visual_memory`**
  - `similarity_threshold` – CLIP similarity cut-off for using visual memory.  
  - `retrieval_alpha` – weight between image vs. description similarity.

These settings are read mainly via `nadine.agents.utils.load_agent_llm` and the visual-memory helpers in `memory_retrieval_agent.py`.

---

## Where to Go Next

- **Interaction Layer / Runtime & MQTT** – deep dive into the DialogueManager, STT/UI, and MQTT topics.  
- **Interaction Layer / Agents & Graph** – detailed description of the LangGraph workflow and each agent.  
- **Interaction Layer / Memory & RAG** – how user profiles, episodic memory, visual memory, and RAG work together.


