# Project Overview – Development & Troubleshooting

This page collects development notes, configuration hints, MQTT topics, and troubleshooting tips.

---

## Configuration

### Environment Variables

Create `.env` files in the relevant component directories with:

- API keys for [Azure Text-to-Speech](https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech) and [Google Cloud](https://cloud.google.com/) services.  
- LLM configuration (e.g. [Ollama](https://ollama.com/) endpoint, API keys).  
- MQTT broker settings (if different from defaults).  

### Agent Toggles

Control which agents are active via environment variables:

- `NADINE_ENABLE_VISION_AGENT` – enable/disable vision agent.  
- `NADINE_ENABLE_MEMORY_AGENTS` – enable/disable memory agents.  

These are read by `graph.py` to skip certain agents when running on resource-constrained systems.

---

## MQTT Topics (Summary)

The system uses MQTT for inter-component communication.

**Perception -> Interaction**

- `nadine/graph/user_detected` – user recognition events.  
- `nadine/graph/face_stored` – face storage confirmations.  

**Interaction -> Control**

- `nadine/agent/control/speak` – text-to-speech requests.  
- `nadine/agent/control/look_at` – gaze (3D position) control commands.  
- `nadine/agent/control/animation` – animation requests.  

**Perception -> Control**

- `nadine/agent/control/look_at` – 3D position for gaze.  

**Interaction -> Perception**

- `nadine/face_recognition/user_info` – user information for face storage.  
- `nadine/perception/capture_current_view` – request the current camera view.  

For topic-by-topic payload details, see the individual Perception, Interaction, and Control layer docs.

---

## Development Tips

### Adding New Agents (Interaction Layer)

1. Create a new agent function under `interaction/nadine/agents/`.  
2. Add the agent as a node in `interaction/nadine/agents/graph.py`.  
3. Update the orchestration agent’s prompt and parsing logic if necessary.  
4. Wire the agent into the graph using `add_node` and `add_conditional_edges`.  

### Extending the Knowledge Base

- Add documents to `interaction/db/knowledge/rag_files/`.  
- They will be indexed automatically by the knowledge RAG pipeline on first use.  

### Custom Animations (Control Layer)

- Add XML animation files to `control/XMLAnimations/` following existing examples.  
- Map them from logical names in `AgentControlHandler` or in higher-level interaction logic.  

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


