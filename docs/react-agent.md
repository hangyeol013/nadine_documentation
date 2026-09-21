# ReAct Platform – Dialogue Manager & Tools

This page documents the interaction layer of `nadine_stable`: how one user turn becomes a spoken reply. The code lives in `interaction_SoR_v2/nadine/dm/`.

---

## Per-Turn Pipeline

`DialogueManager.processInput(text, language)` is called once per final transcript. It normalizes whitespace, logs the input, and calls `NadineReactAgent.execute(input, user_id, user_emotion)`, which runs these steps:

1. **Contextualize.** A separate LLM call (`contextualize_q_prompt | llm`) rewrites the input into a standalone question using the chat history, so follow-ups such as "and tomorrow?" retrieve correctly. The answer is not generated here.
2. **Retrieve long-term memories.** `NadineMemory.retrieve()` queries the user's own ChromaDB collection with the standalone question, top 5. Skipped when the user is `unknown`.
3. **Retrieve knowledge.** `RagManager.retrieve()` queries the knowledge collection, top 3.
4. **Run the ReAct agent.** The retrieved texts, the user's name, the user's facial emotion, and the date and time are placed in the prompt. The agent either calls a tool and loops, or returns a final answer.
5. **Return the structured answer.** The final JSON carries the reply and Nadine's self-assessed emotion; `processInput` returns the reply text and logs the turn duration.

The whole turn is wrapped in `RunnableWithMessageHistory`, keyed by `user_id` and a conversation ID created when the agent starts, so the chat history is threaded through the contextualizer and the agent automatically.

If the agent raises, `processInput` logs the traceback and returns the fixed text "Sorry, I am unable to answer this question." There is no tool-free fallback chain.

The dialogue manager uses one `ChatOpenAI` instance, model `gpt-5.4-mini`, temperature 1, for the agent, the contextualizer, and the knowledge base. Because newer OpenAI models reject the `stop` parameter, no stop sequence is bound; the parser takes the first action in the output and the executor supplies the real observation.

---

## Memory

### Conversation history

`NadineMemory` is a `BaseChatMessageHistory` that keeps an in-process list of messages per user and conversation. Each message is stamped with a Unix timestamp in its metadata. The list is a sliding window of 20 messages.

### Long-term memory

The same class persists conversation chunks to ChromaDB under `data/memory/`, one collection per user, embedded with OpenAI `text-embedding-3-large`:

- When the window first reaches 20 messages, and again every 14 messages after that, the current window is stored as one document. Consecutive chunks therefore overlap by 6 messages.
- When the interaction ends (`end_user_interaction`, called when the user disappears), the remaining messages are stored and the history cleared.
- Each document is the transcript with timestamps and speaker names, plus `date`, `time`, and `conversation_id` metadata.
- Nothing is stored or retrieved for the user `unknown`.

Memories are raw conversation text, not extracted facts. The prompt receives the top 5 chunks under a "LONG-TERM MEMORY" heading and is told to use them if relevant.

### Knowledge base

`RagManager` loads the ChromaDB collection `nadine-knowledge` from `data/knowledge/`, or builds it from the Wikipedia article and the platform PDF if the folder is missing. Retrieval is plain similarity, top 3, on the contextualized question.

---

## The ReAct Agent

`NadineReactAgent` assembles a LangChain `AgentExecutor` from four parts.

**Prompt** (`prompt.py`). A chat prompt with a system message, the chat history, the human turn, and the scratchpad. The human turn is one template with these sections:

- `PHYSICAL SITUATION` (in the system message): where Nadine is, that she speaks by voice with people she sees through a camera, that she is a social robot rather than an assistant, her origin and who she is modeled on.
- `RULES`: answer in the first person; reply in the language of the latest input, defaulting to English, and never mix languages; use formal address in French; be social and polite; react emotionally, and more sharply when insulted; never say you do not understand; use Celsius; use the search tools for anything current; keep answers to two sentences; never repeat an answer; no URLs or code in the reply.
- `TOOLS`: the rendered name and description of every tool.
- `KNOWLEDGE BASE` and `LONG-TERM MEMORY`: the retrieved texts.
- `RESPONSE FORMAT INSTRUCTIONS`: the two output options below.
- `CONTEXTUAL INFORMATION`: user name, the emotion the vision component detected on the user's face, date, and time.
- `HUMAN'S INPUT`.

After a tool runs, the observation is fed back as a human message that reminds the model to answer the original input, to mention information obtained from tools without naming them, and to keep the JSON format.

**Output format.** The model must emit one JSON code block in one of two shapes:

- A tool call: `{"action": "<tool name>", "action_input": "<input>"}`.
- A final answer: `{"action": "Final Answer", "action_input": "<reply>", "category": ..., "emotion": ..., "emotion_intensity": ..., "causing_person": ...}` where `category` is one of greeting, farewell, insult, complement, information request, other; `emotion` is one of joy, sadness, fear, disgust, anger, surprise; `emotion_intensity` is 0 to 10; and `causing_person` is the user's name, `SELF`, `human`, or `SOMEONE ELSE`.

**Parser** (`NadineReactParser`). Parses the JSON from the markdown block. If the model returns a list of actions it takes the first. A `Final Answer` becomes an `AgentFinish` whose output carries the reply and the four emotion fields; anything else becomes an `AgentAction`. Unparseable output raises, and the executor is configured with `handle_parsing_errors=True`, so the error text is fed back to the model for another attempt.

**Executor.** `AgentExecutor(agent, tools, verbose=True, handle_parsing_errors=True)`, wrapped with the memory function.

Nadine's own emotion is appraised on every final answer, but nothing stores it between turns. There is no persistent affective state.

---

## Tools

`DialogueManager.get_tools()` registers the tools below. Search, news, and weather are registered only when their API keys are present in the environment.

| Tool name | The prompt says to use it when | Input | What it does | Needs |
|---|---|---|---|---|
| `Google Search` | Questions about current events, the state of the world, or people | A natural-language question | Serper web search with the Switzerland locale. Rewrites degree symbols to words for weather results and prefixes long results with an instruction to keep the reply under 40 words. | `SERPER_API_KEY` |
| `Google News` | Top headlines of current news | A natural-language question | Serper search of type `news`, same locale and reply-length instruction. | `SERPER_API_KEY` |
| `Weather App` | Current weather for a location | A location string such as `London,GB`; empty input defaults to Carouge, Switzerland | OpenWeatherMap lookup, Celsius, with an instruction to summarize in under 25 words. | `OPENWEATHERMAP_API_KEY` |
| `Nadine behaviour` | The user asks Nadine to smile, be angry, or wave | One of `smile`, `anger`, `wave` | Publishes the matching animation over MQTT, waits two seconds, and returns a sentence for Nadine to say. | – |
| `Sing a song` | The user talks about singing or asks for a song | A song name, `new\|en\|<topic>`, `new\|fr\|<topic>`, `lyrics`, or `any` | Offers the song list, plays a library song, makes up a new song in a background thread, or recites the last made-up lyrics. See [Singing Pipeline](react-singing.md). | – |
| `Languages Switcher` | The user asks Nadine to speak another language | A language name | Matches the name, or any word of a multi-word name, against the `Language` enum and calls back into the main process to switch STT and TTS. Returns a sentence confirming the new language. | – |

`StatementCategories` (greeting, farewell, insult, complement, mapped to smile, wave, and anger animations) exists in `tools.py` but is not registered, so the agent never sees it. An image-generation tool is present only as commented-out code.

Tool observations are written as instructions to Nadine ("Tell the human 'I am smiling now'") rather than as data, which is how a physical action and its verbal acknowledgment stay in one turn.

---

## User Identity, Emotion, and Language

- `user_id` defaults to `unknown` and is set by `Perception.user_recognized()` when a name arrives on `nadine/user/name`. The ID selects the memory collection and appears in the prompt as the user's name. This repository's perception module does not publish names, so in this build the ID changes only if an external publisher provides one.
- `user_emotion` defaults to `neutral` and is set from `nadine/user/emotion`; it is passed into the prompt as text and lowercased.
- Language is owned by the main process. The UI combo box, the `Languages Switcher` tool, and `set_language` all update the STT language; the reply is published to control with the language's locale tag so TTS speaks it explicitly. Before publishing, `MQTTCommunication.ensure_language()` detects the reply's language with `fast-langdetect` and translates it with Google Translate if it does not match. When the session language is not English, the UI shows English translations of both the input and the reply.
- The singing tool is told the current language each turn so it offers only songs in that language, English or French.

---

## Timing and Logging

Every turn logs the user input, the tool calls and their results, the reply, and the elapsed seconds through the shared `LoggersFactory` logger. The executor runs with `verbose=True`, so the model's reasoning and actions are printed to the terminal. `LANGCHAIN_API_KEY` in the environment enables LangSmith tracing if the LangChain tracing variables are also set.
