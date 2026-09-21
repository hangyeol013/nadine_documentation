# Author notes

Open points not resolved from the code; not published.

## docs/platforms.md

the following points are not recorded in commit history or config and should be confirmed or edited before release.
1. "2025 demo deployments" for SoR-ReAct v2: the legacy folders are named nadine_platform_HNF and nadine_UNDRR. State the venues explicitly if you want them named.
2. "LangGraph multi-agent graph, 2025": earliest evidence is legacy/nadine_Dec_25 (git: "palexpo final version", 2025-07-16). Adjust the date if the graph predates this.
3. "SoR" in "SoR-ReAct v2" is not expanded anywhere; add the expansion once here or in the ReAct section.

## nadine_local

- experiments/finetune/exported/Modelfile.* still reference a nadine_Jan_2026 path in `FROM`; `ollama create` fails on a fresh checkout until updated.
- control: `speakEnd()` fires when lip joints go idle, which is before audio ends (documented as current behavior).
