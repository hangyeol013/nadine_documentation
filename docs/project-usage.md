# Project Overview – Usage

This page explains how to start Nadine, both via the main script and per-component.

---

## Quick Start (`start_nadine.sh`)

From the project root:

```bash
./start_nadine.sh
```

This script will:

- Launch the **control** component (robot control server).  
- Launch the **interaction** component (dialogue system).  
- Launch the **perception** component (face recognition).  

Make sure:

- Conda environments are created and available.  
- EMQX MQTT broker is running (see Installation & Setup).  

---

## Startup Options

`start_nadine.sh` supports several flags:

```bash
# Disable vision agent in the interaction graph
./start_nadine.sh --no-vision-agent

# Disable memory agents
./start_nadine.sh --no-memory-agents

# Skip the perception process (no face recognition)
./start_nadine.sh --no-vision-process
```

These are useful for debugging or running Nadine on systems without a camera or without GPU resources for vision.

---

## Manual Component Startup

You can also start each component separately.

### Control Component

```bash
cd control
conda activate nadine_new
./run.sh

# Or with custom paths:
python main.py -voicepath <path> -animationXMLPath <path>
```

### Interaction Component

```bash
cd interaction
conda activate nadine
./run.sh

# Or run without MQTT:
python -m nadine --nomqtt

# Or in chat mode (text-only only, no audio/UI):
python -m nadine --chatmode
```

### Perception Component

```bash
cd perception
conda activate nadine
./run.sh
```

Each component will log its status to its own `logs/` folder and communicate over MQTT as described in the layer-specific docs.


