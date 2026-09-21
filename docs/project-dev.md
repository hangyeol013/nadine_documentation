# Project Overview – Development & Troubleshooting

This page collects development notes, configuration hints, MQTT topics, and troubleshooting tips.

---

## Configuration

### Environment Variables

Two `.env` files hold credentials (see Installation & Setup for the full contents):

- `control/.env` – [Azure Speech](https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech) key and region for text-to-speech.  
- `interaction/.env` – [Google Cloud](https://cloud.google.com/) service-account path and project, Serper key, optional LangSmith and OpenAI keys.  

LLM profiles and the agent-to-profile mapping live in `interaction/config.yaml`; MQTT hosts and ports are in each layer's `config.yaml`.

### Agent Toggles

`graph.py` reads two environment variables at import time and skips the corresponding nodes when they are `0`:

- `NADINE_ENABLE_VISION_AGENT` – vision agent.  
- `NADINE_ENABLE_MEMORY_AGENTS` – memory retrieval and update agents.  

Both default to `1` when the interaction layer is started manually. `start_nadine.sh` sets both to `0`; `start_nadine_chatmode.sh` sets both to `1` (see Usage).

---

## MQTT Topics (Summary)

The system uses MQTT for inter-component communication.

| Topic | Direction | Purpose |
|---|---|---|
| `nadine/graph/user_detected` | Perception → Interaction | Recognized user (name, id, confidence); also sent with empty fields after 5 s without a face. |
| `nadine/graph/face_stored` | Perception → Interaction | Confirmation that a new face image was stored. |
| `nadine/memory/scene_stored` | Perception → (unused) | A memorable scene was stored; published but no layer subscribes to it. |
| `nadine/agent/control/look_at` | Perception → Control | 3D position of the tracked face for gaze. |
| `nadine/face_recognition/user_info` | Interaction → Perception | User name and id to attach to the tracked face. |
| `nadine/perception/capture_current_view` | Interaction → Perception | Request the current camera frame for the vision agent. |
| `nadine/affect/state` | Interaction → Perception | Robot emotion label, arousal, and intensity after each appraisal; drives the memorability decision. |
| `nadine/agent/control/speak` | Interaction → Control | Text to synthesize and speak. |
| `nadine/agent/control/animation` | Interaction → Control | Animation name to play. |
| `nadine/agent/control/look_at_target` | Interaction → Control | Named gaze posture from the UI (interviewer, Zoom, default). |
| `nadine/agent/feedback/start_speak` | Control → Interaction | Speech synthesis started. |
| `nadine/agent/feedback/end_speak` | Control → Interaction | Speech finished; the microphone is re-enabled. |

Control subscribes to the whole `nadine/agent/control/#` tree.

For topic-by-topic payload details, see the individual Perception, Interaction, and Control layer docs.

---

## Development Tips

### Testing Agents

All agents include test harnesses that can be run directly:

```bash
cd interaction/nadine/agents

# Test intent classification
python intention_classifier_test.py

# Test memory update agent
python memory_update_agent.py

# Test orchestration agent
python orchestration_agent.py

# Test search agent
python search_agent.py

# Test vision agent
python vision_agent.py

# Test response agent
python response_agent.py

# Test contextualizer
python context_summarizer.py
```

**Test Samples**: All test cases are centralized in `agent_test_samples.py` for easy maintenance. When adding new test cases, add them to this file and import them in the respective agent test harnesses.

### Adding New Agents (Interaction Layer)

1. Create a new agent function under `interaction/nadine/agents/`.  
2. Add the agent as a node in `interaction/nadine/agents/graph.py`.  
3. Update the orchestration agent's prompt and parsing logic if necessary.  
4. Wire the agent into the graph using `add_node` and `add_conditional_edges`.
5. Add test cases to `agent_test_samples.py` and create a test harness in the agent file.  

### Extending the Knowledge Base

- Add text documents to `interaction/db/knowledge/rag_files/` (create the folder if it does not exist).  
- On the next start the knowledge RAG agent embeds them with the `nomic-embed-text` Ollama model and stores the index in `interaction/db/knowledge/chroma/`; delete that folder to force a rebuild.  

### Custom Animations (Control Layer)

- Add XML animation files to `control/XMLAnimations/` following existing examples.  
- Animations are addressed by the `<animation_name>` value inside the XML, not the filename; publish that name on `nadine/agent/control/animation` or reference it from `interaction/nadine/common/mqtt_comm.py`.  

---

## Troubleshooting

### MQTT Connection Issues

- Ensure Docker Compose services are running:

  ```bash
  docker compose ps
  ```

- Check EMQX broker logs:

  ```bash
  docker compose logs emqx
  ```

- Verify that ports `1883` (MQTT) and `18083` (dashboard) are not blocked.

### Face Recognition Not Working

- Check RealSense camera connection and permissions.  
- Confirm that required models are downloaded and accessible.  
- Look at `perception/logs/` for detailed errors.  

### Audio Issues

- Check PulseAudio / system audio configuration (see `start_nadine.sh`).  
- Verify microphone and speaker permissions.  
- Test with `--nomqtt` to isolate interaction from control/perception issues.  

### LLM Errors

- Verify that Ollama (or your LLM backend) is running.  
- Check API keys in `.env`.  
- Inspect logs in `interaction/logs/` and agent-specific logs if enabled.
- **Invalid JSON Output**: If agents return invalid JSON, check:
  - Prompt length (long prompts can cause issues with small LLMs).
  - Use the test harnesses to debug specific agents.
  - Check that `format="json"` is set in `load_agent_llm()` calls where needed.

### Prompt Optimization

All agent prompts are written for small LLMs (Qwen2.5-1.5B and its fine-tuned variants) to improve:
- **Speed**: Shorter, more directive prompts reduce latency.
- **Accuracy**: Explicit rules and examples guide the LLM to correct outputs.
- **JSON Output**: Prompts explicitly require JSON format with examples.
- **Consistency**: Clear rules reduce variability in outputs.

Key optimization strategies:
- Use explicit, numbered rules instead of verbose explanations.
- Include concrete examples in the prompt.
- Emphasize critical constraints (e.g., "NEVER answer", "Output JSON only").
- Remove unnecessary context that doesn't affect the task.
- Use `format="json"` parameter in `load_agent_llm()` for structured outputs.

When modifying prompts, test with the agent's test harness to ensure performance is maintained.  

---

## Logging

Logs are stored in:

- `control/logs/` – control component logs.  
- `interaction/logs/` – interaction component logs.  
- `perception/logs/` – perception component logs.  
- `mqtt-monitor-logs/` – MQTT monitoring logs.  

Central loggers (`LoggersFactory`) provide consistent formatting across components.

---

## Acknowledgments

Nadine is developed at MIRALab, University of Geneva, under the direction of Professor Nadia Magnenat-Thalmann.


