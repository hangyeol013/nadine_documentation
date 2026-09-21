# Project Overview – Platforms

Nadine's software has been developed as two platform families that share the same perception and control layers but differ in how the interaction layer is built. This page describes the three currently maintained versions, how they relate to each other, and the constraints that shaped each one.

All three versions share the same foundation: an MQTT message bus between three layers, a RealSense camera with YOLOv8 face tracking for [perception](perception-overview.md), Google Cloud speech recognition, Azure text-to-speech, and the XML animation and joint [control](control-overview.md) stack. The two multi-agent versions add InsightFace recognition and selective visual memory on the perception side; the ReAct build tracks the closest face for gaze only and takes the user's name from an external publisher.

| Version | Dialogue engine | Language models | Features |
|---|---|---|---|
| **Multi-Agent, Local** | LangGraph graph, ten agents ([Agents & Graph](interaction-agents.md)) | On-device via Ollama<br>• fine-tuned Qwen2.5-1.5B per agent<br>• Mistral Small 3.2 for responses<br>• Qwen2.5-VL for vision | • profile, episodic and visual memory ([Memory & RAG](interaction-memory-rag.md))<br>• PAD affect model<br>• no per-turn API cost<br>• use: agent development, offline runs |
| **Multi-Agent, Hybrid Cloud** | Same graph; intent, affect and planning merged into one call ([Cloud Configuration](interaction-cloud-config.md)) | Hybrid<br>• gpt-5.4-mini for understanding, response, memory, routing<br>• vision description kept local<br>• local adapters only in legacy mode | • observation-scene memory ([Multimodal Memory](interaction-multimodal-memory.md))<br>• A/B study mode and logging<br>• use: memory research, user studies |
| **ReAct, Cloud** | Contextualizer → memory and knowledge retrieval → ReAct agent with fixed tools ([Dialogue Manager & Tools](react-agent.md)) | Cloud only<br>• gpt-5.4-mini, gpt-4o-mini (OpenAI) | • long-term conversation memory (per named user) and knowledge base<br>• per-turn emotion in the structured answer<br>• barge-in, singing<br>• use: demonstrations, recordings |

The versions live in three repositories: `nadine_local` (Multi-Agent, Local), `nadine_phd` (Multi-Agent, Hybrid Cloud, forked from `nadine_local`), and `nadine_stable` (ReAct, Cloud). The layer documentation on this site describes the multi-agent code base unless a page says otherwise.

---

## Lineage

Both families descend from the MQTT-based three-layer stack introduced in 2025. The ReAct family is the older interaction design and has been kept as the deployment platform; the multi-agent family replaced it for research work and was later split into a local and a hybrid-cloud configuration.

<figure class="platform-figure">
<a href="../assets/platforms_lineage.svg" target="_blank" rel="noopener" title="Open full size">
--8<-- "assets/platforms_lineage.svg"
</a>
<figcaption>Lineage of the three maintained versions. Both families share the MQTT three-layer stack.</figcaption>
</figure>

The two multi-agent versions share one code base. The hybrid-cloud version contains every commit of the local version plus the changes made after the fork, so a feature added to the local graph carries over unless it was deliberately replaced.

---

## Architecture Comparison

Perception and control are common to both families and communicate with the interaction layer over MQTT topics. The interaction layer differs, and the ReAct build carries a lighter perception layer without face recognition.

<figure class="platform-figure">
<a href="../assets/platforms_architecture.svg" target="_blank" rel="noopener" title="Open full size">
--8<-- "assets/platforms_architecture.svg"
</a>
<figcaption>Perception and control are common; the interaction layer is either a LangGraph multi-agent graph or a retrieval-augmented ReAct agent. The dashed outline marks the nodes that the hybrid-cloud version merges into one turn-understanding call.</figcaption>
</figure>

The multi-agent graph separates understanding, memory, affect, and generation into distinct nodes so that each step can be evaluated, swapped, or fine-tuned independently. The ReAct agent (SoR-ReAct v2) keeps retrieval as fixed steps before the loop: a contextualizer rewrites the input into a standalone question using the chat history, and that question retrieves the user's long-term memories and the knowledge base. Everything else happens in one reasoning loop that selects tools and returns a structured answer carrying the reply, an input category, and Nadine's own emotion with its intensity and cause. This keeps the control flow simple and the failure surface small.

The hybrid-cloud version keeps the graph but changes its front half. The intent classifier, affective appraisal, and orchestrator are replaced by a single structured call that returns intent, emotion, and a routing plan together; the rest of the turn is deterministic routing over that plan. The guards that the separate nodes applied, such as the name-confirmation short circuit, are kept around the merged call, and the original three-node pipeline remains available as a configuration option.

---

## Design Rationale

### Multi-Agent, Local

**Constraint.** All inference runs on the robot's workstation. No user speech, camera frames, or memory content leave the machine, and there is no per-turn API cost.

**Consequence.** On-device inference limits the models to a few billion parameters, and generic small models were too slow and too unreliable across ten agent roles. Each agent was therefore fine-tuned as a LoRA adapter on Qwen2.5-1.5B, merged, quantized to GGUF, and registered as its own Ollama model, so every local model is served by one Ollama instance and can be kept resident in GPU memory. The response agent, where quality matters most, runs the larger Mistral Small 3.2 through the same server.

**Cost.** Small fine-tuned models reproduce their training behavior closely. When the memory extraction rules were later tightened, the fine-tuned extractor kept following its original training and recorded stale facts as current ones. Improving that behavior requires new training data and a new adapter rather than a prompt change.

### Multi-Agent, Hybrid Cloud

**Constraint.** The platform was prepared for a user study on multimodal memory, which required reliable memory extraction, stable turn understanding, and predictable latency under continuous use.

**Consequence.** Agents whose failures would corrupt the study data moved to gpt-5.4-mini: turn understanding, the response agent, memory extraction, and the search and vision routers. Merging intent, affect, and planning into one call replaced three sequential local calls and the history contextualizer with one call bounded at 2.5 seconds. Extraction and episodic encoding run at most once per conversation, so the cloud cost of this change is negligible, and moving the routers off the GPU freed VRAM. The original local nodes remain selectable through the legacy pipeline mode.

Vision description stayed local by design. Sending camera frames of study participants to an external provider was a privacy decision, not a latency one.

**Cost.** User speech text and the facts extracted from it now leave the machine; only camera frames stay local. The platform depends on network availability and an API key for its central agents, and its behavior is tied to a hosted model version that can change outside the project's control.

### ReAct, Cloud

**Constraint.** Public demonstrations and recorded sessions need a system that fails rarely and recovers cleanly when it does, in front of an audience and without an operator intervening.

**Consequence.** A single ReAct agent with a fixed tool set has a small, predictable control flow, and cloud models remove the on-device inference path as a failure source. Engineering effort went to the audio and animation path instead of the dialogue model: user interruption (barge-in) with correct lip-sync recovery, Google STT stream-size limits, PulseAudio routing for the TTS SDK, and a singing pipeline with a multilingual song library.

**Cost.** Long-term memory is stored as raw conversation chunks rather than extracted facts and episodes, emotion is appraised per turn without a persistent affective state, and there is no visual memory. Adding a capability means adding a tool rather than a graph node, which is quick but does not scale to the memory and affect work carried out on the multi-agent platform.

