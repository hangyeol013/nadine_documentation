# Interaction Layer – Memory & RAG

This page details how Nadine’s interaction layer manages **user memory** (profiles, episodic memory, visual memory) and **knowledge retrieval** (RAG).

---

## User Profiles (`user_info.json` & `user_ids.json`)

User profile information is stored under:

- `interaction/db/memory/user_profiles/<user_id>/user_info.json`

Each `user_info.json` contains fields like:

- `user_id`, `user_name`
- `current_company`, `current_position`, `location`
- `hobbies`, `interests`
- `face_image_path`
- `last_updated`

The file:

- `interaction/db/user_ids.json`

Maps:

- `user_id` → `user_name`

This mapping is used to quickly resolve names, detect similar names, and coordinate between **interaction** and **perception** layers.

Key helpers:

- `user_info_init(user_id, user_name)` – create a default profile.  
- `fetch_user_info(user_id, user_name)` – load or initialize profile on disk.  
- `update_user_ids(user_id, user_name)` – update `user_ids.json` after name changes.

---

## Memory Update Agent (`memory_update_agent.py`)

The **memory update agent** has two main responsibilities:

1. **Structured user profile updates** based on conversation (e.g., “My name is Alice, I work at Trafigura in Geneva”).  
2. **Episodic memory storage** that summarizes important interaction episodes.

### Structured user profile updates

When `state["intent"] == "update_user_info"`:

- A dedicated LLM (`load_agent_llm("memory_update_agent")`) is prompted to extract structured fields:
  - `user_name`
  - `current_company`
  - `current_position`
  - `location`
  - `hobbies`
  - `interests`
- The output is parsed into a `MemoryUpdate` Pydantic model.
- `save_user_info(...)`:
  - Loads existing `user_info.json` (or initializes one).
  - Merges the new fields (deduplicating hobbies/interests).
  - Updates `last_updated`.
  - Ensures `user_ids.json` is consistent.
  - Handles **name similarity and confirmation**:
    - Computes a similarity score between `user_name` and all names in `user_ids.json` using Levenshtein ratio.
    - If one name is a strong match (`HIGH_SIMILARITY_THRESHOLD`):
      - Immediately links to that existing user and returns the stored profile.
    - If several names are moderately similar (`LOW_SIMILARITY_THRESHOLD`):
      - Returns a `name_confirmation` structure containing:
        - `given_name`, `similar_names`, `similar_ids`, `similarity_scores`.
      - The graph then routes to `response_agent`, which asks the user to confirm the top candidate.
    - If no reasonable match is found:
      - Proceeds as a new user; `name_checked` is set and a new profile is created/updated.

The `update_memory` wrapper in `graph.py` merges the returned `user_info`, `name_checked`, and `name_confirmation` fields back into the graph state. On the next user turn, the **DialogueManager** consumes this state and either accepts a suggested existing user, creates a new one, or rotates to the next suggestion, before finally sending the confirmed `user_name`/`user_id` pair back to perception for face-linking.

### Episodic memory

When `intent != "update_user_info"` (e.g., end of a conversation):

- The agent summarizes the last part of the conversation into an **episode**:
  - Builds a short transcript of recent `Human`/`AI` turns.
  - LLM extracts `observation`, `thought`, `action`, `result` into an `EpisodicSave` model.
- `save_episodic_memory(...)`:
  - Skips save if `user_name` is missing or still `"Unknown"`.  
  - Otherwise:
    - Builds `conversation_text` and `episode_text`.
    - Creates two new documents in Chroma, tagged with:
      - `user_id`
      - `timestamp`
      - `memory_type` = `"conversation"` or `"episode"`.
    - Stores them in a Chroma collection named after the `user_id`.

The result flag `saved` is merged back into the graph state as `episodic_memory` information.

---

## Memory Retrieval (`memory_retrieval_agent.py`)

When the graph needs context about a user, `get_user_specific_memory(state)` is called.

### Textual memory (Chroma)

- Finds the Chroma collection for the current `user_id`.  
- Runs two independent similarity queries based on the latest user message:
  - One over documents where `memory_type == "episode"`.  
  - One over documents where `memory_type == "conversation"`.  
- Returns the closest matching:
  - `episode_memory`
  - `conversation_memory`

If no Chroma collection exists yet, the function degrades gracefully and returns `None` for these fields.

### Visual memory

The same function also calls `_retrieve_best_visual_memory(state, user_id)` to:

- Inspect memorable scenes stored by the **perception layer** under:
  - `interaction/db/memory/user_profiles/<user_id>/memorable_scenes/`
- Use CLIP text embeddings of the current user question to:
  - Compare against stored image embeddings (from perception).
  - Optionally combine similarity with stored scene descriptions.
- Select the most relevant visual memory if its combined similarity exceeds a threshold:
  - Controlled by:
    - `interaction.visual_memory.similarity_threshold`
    - `interaction.visual_memory.retrieval_alpha`

The output is a minimal dict:

- `{"image_path": ..., "scene_id": ..., "similarity": ...}` or `None`.

This is placed in `state["visual_memory"]` and later consumed by the **response agent**:

- `response_agent` attaches the image as an `image_url` content item, so the response LLM can reason over both text and visuals.

---

## Knowledge RAG Agent (`knowledge_RAG_agent.py`)

Nadine’s long-term **system knowledge** lives in:

- `interaction/db/knowledge/rag_files/`

The **knowledge RAG agent** (`get_related_knowledge(state)`) works as follows:

1. On first run:
   - Loads all files from `rag_files/` using `TextLoader`.  
   - Splits them into chunks grouped by markdown headers (`#`, `##`).  
   - Builds a Chroma vectorstore:
     - Embeddings: `OllamaEmbeddings(model="nomic-embed-text")`.  
     - Collection name: `"nadine-knowledge"`.  
     - Persist directory: `interaction/db/knowledge/chroma/`.

2. On later runs:
   - Reuses the existing Chroma collection if present.

3. For each query:
   - Uses the LangGraph state’s last message as the query text.  
   - Retrieves the top 1 most relevant chunk.  
   - Flattens the chunk into a single string (with markup removed).  
   - Optionally:
     - Detects and displays a **visual source** (if indicated in the chunk metadata).  
   - Returns a formatted string summary.

The result is stored in `state["knowledge_retrieval"]` and is passed into the **response agent** as part of the user packet.

---

## Visual Memory Configuration (`interaction/config.yaml`)

The visual memory retrieval behavior is configured via:

```yaml
interaction:
  visual_memory:
    similarity_threshold: 0.6
    retrieval_alpha: 0.7
```

- `similarity_threshold`:
  - Minimum combined CLIP similarity (text–image + text–description) needed to use a visual memory.
- `retrieval_alpha`:
  - Blend factor between:
    - `sim_image` (text vs. image embedding)
    - `sim_desc` (text vs. description embedding)
  - Effective similarity:
    - `alpha * sim_image + (1 - alpha) * sim_desc`

Adjust these values to make visual memory **more or less prominent** in responses.

---

## How Everything Fits Together

On each turn:

1. **Memory retrieval** (`retrieve_memory`):
   - Loads textual + visual memories for the current user.  
   - Passes them to the affective system and orchestrator.

2. **Tools & reasoning** (search, vision, knowledge RAG):
   - Provide up-to-date external and internal knowledge.  

3. **Response agent**:
   - Sees:
     - Conversation + episodic memory summaries.
     - Relevant visual memory (if any).
     - Knowledge chunks from RAG.
   - Generates a response that is both **contextual** and **personalized**.

4. **Memory update** (`update_memory`):
   - Incorporates new user profile data and episodic memories.  
   - Keeps `user_info`, Chroma DB, and `user_ids.json` in sync over time.

Together, these components make Nadine’s interactions **cumulative**, **personalized**, and **multimodal** across sessions.


