# Interaction Layer – Cloud Configuration (nadine_phd)

The Hybrid Cloud version (`nadine_phd`) runs the same LangGraph interaction layer as `nadine_local`, but moves the agents that matter most for reliability to hosted models and replaces the front of the graph with one structured call. This page documents what changed and how to operate it. The graph itself, the agents, and the memory system are described on the [Overview](interaction-overview.md), [Agents & Graph](interaction-agents.md), and [Memory & RAG](interaction-memory-rag.md) pages; the reasons for the split are on the [Platforms](platforms.md) page.

---

## Agent-to-Model Mapping

`interaction/config.yaml` maps each agent to an LLM profile. The mapping is the same file in both pipeline modes; the mode decides which agents run.

| Agent | Profile | Backend / model | Where | Pipeline mode |
|---|---|---|---|---|
| `turn_understanding` | `understand_gpt` | OpenAI `gpt-5.4-mini` | cloud | merged only |
| `response_agent` | `response_gpt` | OpenAI `gpt-5.4-mini` | cloud | both |
| `memory_update_agent` | `gpt_json` | OpenAI `gpt-5.4-mini` | cloud | both |
| `search_router` | `gpt_json` | OpenAI `gpt-5.4-mini` | cloud | both |
| `vision_router` | `gpt_json` | OpenAI `gpt-5.4-mini` | cloud | both |
| `vision_description` | `vision_llm` | Ollama `qwen2.5vl:3b` | local | both |
| `intention_classifier` | `ft_intent_classifier` | Ollama `nadine-intent_classifier` | local | legacy only |
| `affective_appraisal` | `ft_affective_appraisal` | Ollama `nadine-affective_appraisal` | local | legacy only |
| `orchestration_agent` | `ft_orchestration_agent` | Ollama `nadine-orchestration_agent` | local | legacy only |
| `contextualizer` | `ft_episodic_memory` | Ollama `nadine-episodic_memory` | local | legacy only |

In `merged` mode the four local fine-tuned agents are never invoked: the `understand` node produces their outputs in one call, and the contextualizer is only called from inside the legacy orchestrator. Text memory retrieval and storage use no LLM in either mode; they embed with the local `ONNXMiniLM_L6_V2` function as in `nadine_local`.

The config comments record why each cloud move was made:

- `memory_update_agent` (was `ft_memory_update`): the fine-tuned model "reproduces its training behavior and ignores the hardened extraction rules — it recorded 'I was supervising you in Singapore' as current job/location. Extraction and episodic encoding run at most once per conversation, so cloud cost is negligible."
- `search_router` and `vision_router` (were `small_llm`): they "only run on search/vision turns (which already pay a web/camera round trip), and the cloud model is far more reliable at instruction-following. Frees router VRAM on GPU 1."
- `vision_description` "stays LOCAL deliberately: switching to `vision_gpt` would send camera frames of participants to OpenAI — a study-privacy decision, not a latency one."

---

## LLM Profiles

### Backend resolution

`load_agent_llm(agent_name)` in `nadine/agents/utils.py` resolves the profile in this order:

1. `NADINE_PROFILE_<agent_name>` environment variable, if set (for example `NADINE_PROFILE_response_agent=claude_response` points one agent at Claude for an A/B run without editing the config).
2. `interaction.agents.<agent_name>` in `config.yaml`.
3. The agent's built-in default (`gpt_json` for `turn_understanding`, `response_llm` for `response_agent`, `big_llm` otherwise).

The profile's `backend` key selects the client: `openai`, `anthropic`, `vllm`, or, when absent, `ollama`. Instances are cached per effective parameter set, so one HTTP connection and one model handle are reused across turns.

### Cloud profiles

| Profile | Backend | Model | temperature | max_tokens | timeout | JSON |
|---|---|---|---|---|---|---|
| `understand_gpt` | openai | `gpt-5.4-mini` | 0.0 | 300 | 2.5 s | yes |
| `response_gpt` | openai | `gpt-5.4-mini` | 0.3 | 160 | 15.0 s | no |
| `gpt_json` | openai | `gpt-5.4-mini` | 0.0 | 300 | 2.5 s | yes |
| `gpt_text` | openai | `gpt-5.4-mini` | 0.0 | 120 | 2.5 s | no |
| `vision_gpt` | openai | `gpt-5.4-mini` | 0.0 | 150 | 2.5 s | no |
| `claude_understand` | anthropic | `claude-haiku-4-5` | 0.0 | 300 | 2.5 s | prompt-only |
| `claude_response` | anthropic | `claude-haiku-4-5` | 0.3 | 500 | 15.0 s | no |
| `gpt4o_mini` | openai | `gpt-4o-mini` | 0.0 | 100 | none | no |
| `gpt4o_mini_long` | openai | `gpt-4o-mini` | 0.3 | 500 | none | no |

`vision_gpt`, the two Claude profiles, and the two `gpt-4o-mini` profiles are defined but not mapped to any agent by default.

Profile keys and their effect:

- `timeout` is the per-call limit in seconds; `max_retries` (default 2) re-issues a call that hits it. The loader comment states the purpose: "a call stuck in the server-side slow tail is aborted at `timeout` and retried (the retry almost always lands on the fast path). Tune `timeout` above p95 (~2.2s) so it never fires on healthy calls." The 2.5 s value on the per-turn calls follows that rule; the response agent gets 15 s because it streams a full reply.
- `format: json` on an OpenAI profile sets `response_format: {"type": "json_object"}`. Claude has no equivalent, so `claude_understand` relies on the prompt's JSON-only instruction and on `JsonOutputParser` stripping any markdown fences.
- `max_tokens` replaces the Ollama `num_predict`; `num_ctx` and `repeat_penalty` are ignored by cloud backends.

### Connection handling

- All OpenAI instances share one `httpx.Client` with 10 keep-alive connections, a 300 s keep-alive expiry, a 60 s request timeout, and a 10 s connect timeout.
- `DialogueManager` calls `start_cloud_keepalive()` at startup. If any mapped profile uses a cloud backend, a daemon thread sends a one-token request per provider every 60 s so the first turn after an idle gap does not pay a reconnect.
- The Anthropic client is imported lazily, so `langchain_anthropic` is only needed when a Claude profile is mapped or selected through the environment override.

---

## Merged Turn-Understanding Pipeline

### Mode selection

`interaction.pipeline.mode` in `config.yaml` is `merged`. The `NADINE_PIPELINE_MODE` environment variable overrides it (`merged` or `legacy`); when neither is set the code defaults to `legacy`. The mode is read once when the graph is built.

### The `understand` node

`turn_understanding.py` defines a Pydantic schema, `TurnUnderstanding`, that one call must fill:

- `intent` – one of `first_greeting`, `update_user_info`, `end_conversation`, `language_change`, `continue_conversation`.
- `emotion` – Nadine's own appraised reaction, `{label, intensity}` with the seven labels `happy`, `sad`, `angry`, `fearful`, `disgusted`, `surprised`, `neutral` and intensity 0.0–1.0. This drives tone and the PAD state.
- `user_emotion` – the user's currently felt emotion in the same form. This drives selective scene storage in perception and is rated only for emotions felt now, not ones recalled or mentioned.
- `is_recall` – true when the user asks Nadine to remember anything from the past or earlier in the conversation. This gates text-memory injection and the permissive visual-recall threshold.
- `plan` – a list of `{agent, message}` steps over `search_agent`, `knowledge_rag_agent`, `vision_agent`, `response_agent`.

The prompt carries the routing rules that the fine-tuned orchestrator learned from data, in text: real-time facts go to search, questions about Nadine herself and her own past experiences go to the knowledge agent, anything visual goes to vision, and recall of the user's own information or shared moments goes straight to the response agent because the profile and any matching scene are already loaded. The chat history is passed as plain text in the same call, which is why the contextualizer is not needed.

### Guards around the call

`understand()` in `graph.py` wraps the call in the same deterministic checks the three legacy nodes applied, plus a few added for the study:

- A pending name confirmation short-circuits to `update_user_info` before any model call.
- On any exception the node falls back to `continue_conversation`, neutral emotion, and a single `response_agent` step.
- Unknown intents become `continue_conversation`. The legacy regex overrides still apply: a name introduction upgrades `first_greeting` to `update_user_info`; a question about Nadine downgrades `update_user_info`; `end_conversation` needs an explicit farewell word. One addition: an unambiguous farewell that is not a question is upgraded to `end_conversation` regardless of the model output, because that intent gates the episodic save, the language reset, and the wave.
- `language_change` sets the language and is then treated as `continue_conversation`. `first_greeting` is accepted once per user.
- The emotion label is converted with the same `emotion_to_pad` lookup and `update_affect_state` as the legacy appraisal node.
- The plan is filtered to known agents; greetings and goodbyes always get a single `response_agent` step.

After the appraisal the node publishes `nadine/affect/state`. Compared with `nadine_local` the payload carries four more fields: `user_label`, `user_intensity`, `user_message` (the current utterance, truncated to 500 characters, used as the scene anchor), and `suppress_storage` (true on recall turns and goodbyes, so those turns do not create scenes).

### Routing after the call

`_route_by_plan()` contains no model call. It sends the turn to the first planned sub-agent, or to `response_agent` when the plan is empty or a name confirmation is pending. The merged wiring is:

```
START → understand
  ├─ intent == update_user_info → memory_update_agent → (response_agent | END | memory_retrieve_agent)
  └─ otherwise                  → memory_retrieve_agent
memory_retrieve_agent → [search_agent | vision_agent | knowledge_rag_agent]* → response_agent
response_agent → affective_update → (intent == end_conversation → memory_update_agent | END)
```

Each sub-agent pops its step and re-routes on the remaining plan, as in the legacy graph. `affective_update` still runs after the response but only keeps the state that the appraisal already set.

### What it changed

Per turn, three sequential local calls (intent, appraisal, orchestration) and the contextualizer are replaced by one cloud call bounded at 2.5 s. The design note in `turn_understanding.py` states the premise: the three tasks "are independent functions of (user message, history), so a single capable model can produce all three at once." The module was first scored standalone against the existing intent, routing, and emotion sample sets before the graph was rewired.

---

## Memory Extraction and Knowledge RAG

### Profile extraction rules

`memory_update_agent.py` runs on `gpt_json`. Its extraction prompt is stricter than the version the local adapter was trained on:

- Only facts stated as currently true about the user are extracted; past-tense statements ("I worked at…", "I used to live in…") are memories, not profile fields.
- Statements about the user's shared history with Nadine ("I was supervising you", "your face was modeled on mine") never fill `current_company`, `current_position`, or `location`.
- `location` means where the user lives now, not places mentioned or visited.

The profile schema (`user_name`, `current_company`, `current_position`, `location`, `hobbies`, `interests`) and the identity-conflict guard are unchanged from `nadine_local`; only the rules and the model changed.

### Episodic encoding

The episodic summary prompt now requires the model to preserve the user's concrete claims (names, relationships, biographical and shared-history statements) in the `observation` and `result` fields, because generic summaries were dropping exactly the details that later recall depends on. The loader requests 220 output tokens for this call; that override only applies to the Ollama backend, so on `gpt_json` the profile's `max_tokens: 300` is the effective limit.

### Knowledge RAG

`knowledge_RAG_agent.py` embeds with OpenAI `text-embedding-3-large` instead of the local `nomic-embed-text` model. The code comment gives the reason: "markedly better ranking than the local nomic-embed-text, and consistent with the visual memory description channel which already uses this model." Two further changes:

- Documents are split with `MarkdownHeaderTextSplitter` on both `#` and `##`, and each chunk is prefixed with its header path. Splitting on `##` only had glued top-level headers onto the end of the previous chunk.
- The retriever returns `k=3` chunks instead of one, because Nadine's experiences span several sections and the single nearest chunk was often a related but wrong one.

The index under `db/knowledge/chroma` is specific to the embedding model. After changing the model, delete that directory so it is rebuilt from the markdown files in `db/knowledge/rag_files`.

---

## Running This Configuration

### Keys and environment

`interaction/.env` must contain `OPENAI_API_KEY`; the default mapping does not start without it. Other entries:

- `ANTHROPIC_API_KEY` – only for the Claude profiles.
- `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `SERPER_API_KEY` – unchanged from `nadine_local`.
- `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` – present but tracing was disabled after the monthly trace quota was exhausted. In study mode every prompt and completion is logged locally by `nadine/common/prompt_logger.py` instead.

The conda environment pins `openai==2.15.0` and `anthropic==0.76.0`.

### Local models still required

Ollama still serves `qwen2.5vl:3b` for vision description and, in legacy mode, the fine-tuned `nadine-*` models. `start_nadine.sh` pre-warms only `nadine-memory_update` and `qwen2.5:1.5b-instruct` in Step 1 and `qwen2.5vl:3b` in Step 3 (skipped with `--no-vision-agent`); `mistral-small3.2` is no longer warmed because the response agent is on the cloud. The script's own comment notes that the fine-tuned classifiers "are only used by the LEGACY fallback" and "warm on first use there." The two models it does pre-warm are not used by the default mapping either, so on the default path the only local model that matters at runtime is the vision model.

### Start script differences

Relative to `nadine_local`, the `nadine_phd` launcher enables the vision and memory agents by default and adds `--no-visual-memory`, `--study`, and `--zoom-audio`. Those flags concern the study and the audio path rather than the cloud configuration and are listed on the [Usage](project-usage.md) page.

### Language

The default language is English. `interaction.runtime.current_language` in `config.yaml` only seeds the value; the running language is persisted in `db/runtime_language.json` by `language_config.py`, and the config file is no longer rewritten at runtime.

---

## Known Constraints

- **Network dependency.** Turn understanding, the response, memory extraction, and both routers need the OpenAI API. Each call is bounded by its profile timeout and retried twice; if the API is unreachable, `understand` falls back to a neutral `continue_conversation` turn routed to the response agent, which then fails in the same way.
- **Hosted model drift.** The behavior of every cloud agent is tied to the hosted `gpt-5.4-mini` version, which can change outside the repository.
- **Data leaving the machine.** User speech text, the conversation history passed as context, extracted profile facts, episodic summaries, and knowledge-base chunks are sent to OpenAI. Camera frames, the vision description, face embeddings, and the text-memory embeddings stay local.
- **Two embedding models.** Knowledge RAG uses OpenAI embeddings while user text memory keeps the local ONNX MiniLM model; the two indexes cannot be queried with each other's vectors.
- **Legacy mode still needs the adapters.** Switching to `NADINE_PIPELINE_MODE=legacy` requires all `nadine-*` Ollama models to be present and loads them on first use rather than at startup.
