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
  - LLM profiles: generic Ollama models (`small_llm`, `big_llm`, `response_llm`, `vision_llm`), fine-tuned Ollama models (`ft_*`), and optional cloud profiles (`gpt4o_mini`, `gpt4o_mini_long`, unmapped by default).
  - Agent → LLM profile mapping (most agents use the fine-tuned profiles).
  - vLLM server URL, used only by profiles that set `backend: vllm` (none by default).
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
  - `language_config.py` – persisted runtime language (`get_current_language`, `set_current_language`, `coerce_language`); the default is French.
  - `translation.py`, `translation_llm.py` – text translation tools.
  - `mqtt_comm.py` – interaction-layer MQTT client and helpers.

- **`nadine/stt/`**
  - `google_stt.py`, `stt.py` – [Google Cloud Speech-to-Text](https://cloud.google.com/speech-to-text) integration and microphone handling.

- **`nadine/ui/`**
  - `ui.py` – Tkinter window for monitoring interactions (user text, agent reply, status), a language selector, and a gaze-direction control that publishes look-at targets to the control layer.

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
   - Syncs state with any detected face-recognition user (a user switch saves the outgoing user's episodic memory and resets history and state).
   - Answers a few requests directly without the graph (jokes, "stop talking"); a handshake request triggers the handshake animation.
   - Appends the user message to chat history.
   - Runs the LangGraph multi-agent workflow:
     - Intent classification
     - Memory retrieval/update
     - Affective appraisal
     - Contextualizer (generates conversation context from history)
     - Orchestrator (routes to sub-agents using context)
     - Sub-agents (search, vision, knowledge RAG)
     - Response generation
   - Produces a final response text (and affect state).
4. UI is updated (user input + agent output).  
5. **MQTTCommunication.speak** sends the English response (translated to target language if needed) over:
   - `nadine/agent/control/speak`
6. After speaking finishes, STT is re-activated to listen for the next utterance. If the intent was `end_conversation`, the language is reset to the default (French).

In **chat mode**, steps are similar but:

- No STT or UI.  
- The loop is a simple input/print REPL calling `DialogueManager.processInput`.

---

## Configuration (`interaction/config.yaml`)

The interaction config binds agents to LLM profiles and tunes visual memory:

- **`interaction.vllm`**
  - `base_url` – URL of a vLLM server (default: `http://localhost:8000/v1`). Only used by profiles with `backend: vllm`; no profile sets it in this version, so all local models go through Ollama.

- **`interaction.llm`**
  - **Generic Ollama profiles**:
    - `small_llm` – `qwen2.5:1.5b-instruct` (fallback for simple tasks).
    - `big_llm` – `mistral-small3.2:latest` (heavier reasoning).
    - `response_llm` – `mistral-small3.2:latest` (main conversation LLM, T=0.3).
    - `vision_llm` – `qwen2.5vl:3b` (vision agent).
  - **Fine-tuned Ollama profiles** (Qwen2.5-1.5B LoRA adapters merged, exported to GGUF, and registered as `nadine-*` models; see Installation & Setup):
    - `ft_intent_classifier` – `nadine-intent_classifier`, intent classification.
    - `ft_orchestration_agent` – `nadine-orchestration_agent`, routing plan.
    - `ft_affective_appraisal` – `nadine-affective_appraisal`, emotion appraisal.
    - `ft_memory_update` – `nadine-memory_update`, memory extraction.
    - `ft_episodic_memory` – `nadine-episodic_memory`, episodic summarization.
    - `ft_search_router` – `nadine-search_router`, search routing (defined but not mapped to an agent by default).
  - **Cloud profiles** (`backend: openai`): `gpt4o_mini`, `gpt4o_mini_long`. Defined for experiments; not mapped to any agent by default.
  - A profile may also set `backend: vllm` to use a vLLM server at `interaction.vllm.base_url`; nothing uses this by default.

- **`interaction.agents`**
  - Maps logical agents to LLM profiles. Most agents use the **fine-tuned profiles**:
    - `intention_classifier` → `ft_intent_classifier`
    - `orchestration_agent` → `ft_orchestration_agent`
    - `affective_appraisal` → `ft_affective_appraisal`
    - `memory_update_agent` → `ft_memory_update`
    - `contextualizer` → `ft_episodic_memory`
    - `search_router` → `small_llm`
    - `search_answer` → `small_llm`
    - `vision_router` → `small_llm`
    - `vision_description` → `vision_llm` (Ollama)
    - `response_agent` → `response_llm` (Ollama, Mistral Small 3.2)

- **`interaction.visual_memory`**
  - `similarity_threshold` (0.15) – minimum combined CLIP similarity for a stored scene to be used.  
  - `retrieval_alpha` (0.3) – weight of the image similarity versus the description similarity; at 0.3 the scene description counts more than the image.

These settings are read mainly via `nadine.agents.utils.load_agent_llm` and the visual-memory helpers in `memory_retrieval_agent.py`.

---

## Where to Go Next

- **Interaction Layer / Runtime & MQTT** – deep dive into the DialogueManager, STT/UI, and MQTT topics.  
- **Interaction Layer / Agents & Graph** – detailed description of the LangGraph workflow and each agent.  
- **Interaction Layer / Memory & RAG** – how user profiles, episodic memory, visual memory, and RAG work together.

---

!!! note "Differences in the Hybrid Cloud version (nadine_phd)"
    The `nadine_phd` fork keeps this code base and adds:

    - **Merged pipeline.** With `interaction.pipeline.mode: merged`, a single `understand` node (`turn_understanding.py`) replaces `intention_classifier`, `affective_appraisal`, and `orchestrator`; it returns intent, emotion, and the routing plan in one structured call. The three-node pipeline remains available as `legacy`.
    - **Cloud profiles.** Profiles with `backend: openai` (gpt-5.4-mini: `understand_gpt`, `response_gpt`, `gpt_json`, `gpt_text`, `vision_gpt`) and `backend: anthropic` (claude-haiku-4-5: `claude_response`, `claude_understand`). By default `turn_understanding`, `response_agent`, `memory_update_agent`, `search_router`, and `vision_router` use the OpenAI profiles; `intention_classifier`, `affective_appraisal`, `orchestration_agent`, and `contextualizer` stay on the local fine-tuned models, and `vision_description` stays local so camera frames never leave the machine.
    - **Observation memory.** `observation_memory.py` stores user-directed vision moments as observation scenes, and `visual_memory` gains `recall_threshold` and `first_meeting_recall_threshold` (with `similarity_threshold: 0.35`, `retrieval_alpha: 0.0`).
    - **Study logging.** A per-session `StudyLogger` (`common/study_logger.py`) records timestamped transcripts, memory events, and latency fields.


