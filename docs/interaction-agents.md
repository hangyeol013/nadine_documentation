# Interaction Layer – Agents & Graph

This page documents the **multi-agent graph** that powers Nadine’s dialogue, how each agent behaves, and how they are wired together using LangGraph.

---

## Overview of the Agent Graph (`graph.py`)

The core of the interaction layer is a LangGraph `StateGraph` defined in `nadine/agents/graph.py`.

Key components:

- **CustomState** (`state_schema.py`):
  - Holds:
    - `messages` (chat history)
    - `user_info` (ID, name, profile)
    - `conversation_memory`, `episode_memory`
    - `visual_memory`
    - `search_results`, `vision_results`, `knowledge_retrieval`
    - `intent`, `affect`, `plan_steps`, `language`
    - `name_confirmation`, `name_checked`

- **Top-level nodes**:
  - `intention_classifier`
  - `memory_update_agent` / `memory_retrieve_agent`
  - `affective_appraisal` / `affective_update`
  - `orchestrator`
  - Tool agents: `search_agent`, `vision_agent`, `knowledge_rag_agent`
  - `response_agent`

- **Execution entry**:
  - `build_agent_graph()` returns a compiled workflow used by `DialogueManager`.

---

## Intent Classifier

**Function**: `classify_intent(state: CustomState) -> CustomState`

Responsibilities:

- Reads the latest user message from `state["messages"][-1].content`.  
- Uses a dedicated LLM (via `load_agent_llm("intention_classifier")`) to classify the message into one of:
  - `first_greeting`
  - `update_user_info`
  - `end_conversation`
  - `language_change`
  - `continue_conversation`

Special behavior:

- If `language_change` is detected, tries to infer the requested language from the message content and updates `state["language"]` accordingly, then collapses intent back to `continue_conversation`.
- If `state["name_confirmation"]` contains `similar_names` and `name_checked` is `False`, forces `intent = "update_user_info"` so memory update logic can resolve the name.

Graph wiring:

- From `START` → `intention_classifier`.  
- Conditional edges:
  - To `memory_update_agent` if `intent == "update_user_info"`.
  - Otherwise to `memory_retrieve_agent`.

---

## Memory Retrieval & Update Agents

### Memory Retrieval (`memory_retrieve_agent`)

**Function**: `retrieve_memory(state: CustomState) -> CustomState`

- If memory agents are disabled (`NADINE_ENABLE_MEMORY_AGENTS=0`), logs and returns immediately.  
- Otherwise:
  - Calls `get_user_specific_memory(state)` from `memory_retrieval_agent.py`:
    - Loads user profile from disk (`user_info.json`).
    - Queries Chroma DB for:
      - Best matching **episode** memory (events).
      - Best matching **conversation** memory (past exchanges).
    - Queries **visual memory** (memorable scenes) using CLIP similarity.
  - If name confirmation is needed, places details into `state["name_confirmation"]`.  
  - Otherwise, updates:
    - `state["user_info"]`
    - `state["conversation_memory"]`
    - `state["episode_memory"]`
    - `state["visual_memory"]`

Graph wiring:

- From `intention_classifier` or `memory_update_agent` (depending on conditions).  
- Next:
  - `affective_appraisal` → `orchestrator`.

### Memory Update (`memory_update_agent`)

**Function**: `update_memory(state: CustomState) -> CustomState`  
Wrapper around `memory_update_agent(state)` in `memory_update_agent.py`.

Behaviors:

- If memory agents are disabled, returns immediately.  
- Skips update if name confirmation is still pending.  
- Builds a `mem_state` with:
  - `messages`, `user_info`, `intent`, `name_checked`.
- Calls `memory_update_agent(mem_state)` to:
  - Extract user profile fields from conversation (name, company, location, hobbies, interests).
  - Save/update `user_info.json` and `user_ids.json`.
  - Optionally summarize and save episodic memory to Chroma.
- Merges results back into `state`:
  - `user_info`, `name_checked`, `name_confirmation`, `episodic_memory` flags, etc.
- If `name_checked` and `user_info` are valid:
  - Sends name and ID to perception via:
    - `mqtt_comm.send_user_info_to_face_recognition(user_name, user_id)`

Graph wiring:

- Conditional edge from `intention_classifier`: `update_user_info` → `memory_update_agent`.  
- From `memory_update_agent`:
  - If `name_confirmation` present → `response_agent` (ask the user to confirm).  
  - If `intent == "end_conversation"` → `END`.  
  - Else → `memory_retrieve_agent` (normal flow).

### Name confirmation flow (high-level)

The name confirmation logic is split between the **memory update agent** and the **DialogueManager**:

1. **User shares their name** (e.g., “My name is Alex”):  
   - The intent classifier sets `intent = "update_user_info"`.  
   - `memory_update_agent` extracts `user_name="Alex"` and compares it against names in `user_ids.json` using fuzzy matching.
2. **Three possible outcomes** from `save_user_info`:
   - **Strong match** (score ≥ `HIGH_SIMILARITY_THRESHOLD`):  
     - Immediately link to the existing profile for that user ID.  
     - Return updated `user_info` and `name_checked=True` with no `name_confirmation`.
   - **Ambiguous match** (between `LOW_SIMILARITY_THRESHOLD` and `HIGH_SIMILARITY_THRESHOLD`):  
     - Return a `name_confirmation` payload with:
       - `given_name`, `similar_names`, `similar_ids`, `similarity_scores`.  
     - The graph routes to `response_agent`, which asks the user to confirm the **top** suggested name (e.g., “Is your name Alice?”).
   - **No match** (below `LOW_SIMILARITY_THRESHOLD`):  
     - Proceed as a new user; create/update a profile with `user_name` and mark `name_checked=True`.
3. **User answers the confirmation question**:  
   - On the next turn, `DialogueManager.name_confirmation(user_input)` inspects `state["name_confirmation"]` and the user’s reply:
     - If the user says “yes / correct / that’s me”, the top candidate user ID is accepted and the full stored profile is loaded.  
     - If the user clearly states a different name (e.g. “No, I’m Alice Smith”), a **new profile** is created/updated for that name.  
     - If only one candidate remains and the user doesn’t explicitly confirm, the `given_name` may be taken as the new canonical name.  
     - Otherwise, the candidate list is rotated (pop the first suggestion) and another confirmation question will be asked later.
   - In every resolved case:
     - `name_checked=True`, `name_confirmation={}`.  
     - `send_user_info_to_face_recognition(user_name, user_id)` is called, so perception stores/updates face embeddings under the correct ID.

This loop ensures that:

- Faces, memories, and conversations are consistently linked to the **correct** user ID.  
- Ambiguous matches never silently overwrite existing users; they’re always confirmed explicitly in dialogue.

---

## Affective System

### Affective Appraisal

**Function**: `affective_appraisal(state: CustomState) -> CustomState`

- Ensures `state["affect"]` has subkeys:
  - `personality`, `emotion`, `mood`, `params`.
- Uses `appraise_event_with_llm(...)` from `affective_system.py` to:
  - Take the latest user message and contextual info (e.g. retrieved episode memories).  
  - Produce a new emotion label/intensity.
- Calls `update_affect_state(...)` to update PAD mood/emotion state.

Graph wiring:

- From `memory_retrieve_agent` → `affective_appraisal` → `orchestrator`.

### Affective Update

**Function**: `affective_update(state: CustomState) -> CustomState`

- Post-response hook (after `response_agent`).  
- Currently a pass-through, but is a good place to:
  - Increment turn counters,  
  - Adjust mood based on interaction outcome, etc.

Graph wiring:

- From `response_agent` → `affective_update`.  
- Conditional edge:
  - If `intent == "end_conversation"` → `memory_update_agent` (for final episodic save).  
  - Else → `END`.

---

## Orchestrator & Sub-Agents

### Orchestrator (`orchestrate`)

**Function**: `orchestrate(state: CustomState) -> CustomState`

- Ensures `state["plan_steps"]` is a list.  
- If a plan already exists, returns immediately.  
- Otherwise:
  - Builds an `orchestration_agent()` chain from `orchestration_agent.py`.  
  - Passes:
    - `chat_history` (all messages except the latest).  
    - Latest user message.
  - Receives a JSON “plan” describing a sequence of steps, e.g.:
    - `search_agent`, `knowledge_rag_agent`, `vision_agent`, `response_agent`.
  - Stores the plan in `state["plan_steps"]`.

Graph wiring:

- From `affective_appraisal` → `orchestrator`.  
- Conditional edges:
  - If `plan_steps` empty → `response_agent`.  
  - Else → first planned agent, e.g. `search_agent`, `vision_agent`, or `knowledge_rag_agent`.

### Search Agent (`get_search_results`)

**Function**: `get_search_results(state: CustomState) -> CustomState`

- Uses `search_agent()` to run a question-answering pipeline (web or external search).  
- Takes `state["plan_steps"][0]["message"]` as the query.  
- Stores the result in `state["search_results"]`.  
- Pops the executed step from `plan_steps`.

Graph wiring:

- From `orchestrator` → `search_agent`.  
- Conditional edge:
  - If `plan_steps` is now empty → `response_agent`.  
  - Else → `orchestrator` (to schedule remaining steps).

### Vision Agent (`get_vision_results`)

**Function**: `get_vision_results(state: CustomState) -> CustomState`

- If vision agents are disabled (`NADINE_ENABLE_VISION_AGENT=0`):
  - Logs and sets `state["vision_results"]` to a fallback string.  
- Otherwise:
  - Calls `vision_agent()` with the user question from `plan_steps`.  
  - Stores the result in `state["vision_results"]`.  
- Pops the executed step from `plan_steps`.

Graph wiring:

- From `orchestrator` → `vision_agent`.  
- Conditional edge:
  - If `plan_steps` empty → `response_agent`.  
  - Else → `orchestrator`.

### Knowledge RAG Agent (`get_knowledge_retrieval`)

**Function**: `get_knowledge_retrieval(state: CustomState) -> CustomState`

- Calls `get_related_knowledge(state)` from `knowledge_RAG_agent.py`.  
- This function:
  - Builds/loads a Chroma vectorstore from `interaction/db/knowledge/rag_files/`.  
  - Uses `OllamaEmbeddings` to embed knowledge sections.  
  - Retrieves top‑k relevant chunks for the current question.  
  - Optionally displays related visuals in the UI.  
- Stores the retrieved text in `state["knowledge_retrieval"]`.  
- Pops the executed step from `plan_steps`.

Graph wiring:

- From `orchestrator` → `knowledge_rag_agent`.  
- Conditional edge:
  - If `plan_steps` empty → `response_agent`.  
  - Else → `orchestrator`.

---

## Response Agent

**Function**: `get_final_response(state: CustomState) -> CustomState`

Wrapper around `response_agent()` from `response_agent.py`:

- If `state["name_confirmation"]` contains `similar_names`, returns early to trigger a name-confirmation prompt.  
- Otherwise:
  - Clears `plan_steps`.  
  - Calls `response_agent()(state)`:
    - Builds a composite user packet with:
      - Search, vision, knowledge results.
      - Current time/date.
      - Affective state (emotion + mood text).
      - Optional visual memory image (encoded as a data URL).
    - Sends a system prompt describing Nadine’s persona and language rules.
    - Invokes the configured `response_llm`.
    - Returns the final message text.
  - Writes the response into `state["final_message"]`.  
  - Resets:
    - `conversation_memory`, `episode_memory`,
    - `search_results`, `vision_results`, `knowledge_retrieval`.

Graph wiring:

- Called from many points:
  - Directly after `orchestrator` if no tools are needed.  
  - After tool agents if `plan_steps` is empty.  
  - From `memory_update_agent` when name confirmation is required.  
- After `response_agent`, the graph always goes to `affective_update`.

---

## Putting It All Together

For each user input, the graph runs roughly:

1. `intention_classifier` → classify the message.  
2. `memory_update_agent` (for profile updates) or `memory_retrieve_agent` (for context recall).  
3. `affective_appraisal` → update emotion/mood.  
4. `orchestrator` → decide which sub-agents (if any) to call.  
5. `search_agent` / `vision_agent` / `knowledge_rag_agent` (optional).  
6. `response_agent` → final reply.  
7. `affective_update` → finalize affect and optionally trigger further memory updates.

Detailed memory mechanics are documented on the **Interaction Layer / Memory & RAG** page.


