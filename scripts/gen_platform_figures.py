"""Generate the two Platforms-page figures as theme-aware inline SVG."""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"

MA = "#3f51b5"   # multi-agent accent (Material indigo)
RA = "#00897b"   # ReAct accent (teal)
SH = "#78909c"   # shared / neutral (blue-grey)

STYLE = """
<style>
  .fig { font-family: var(--md-text-font-family, Roboto, Helvetica, Arial, sans-serif); color: var(--md-default-fg-color, #222); }
  .fig text { fill: currentColor; }
  .fig .t  { font-size: 14px; }
  .fig .b  { font-size: 14px; font-weight: 700; }
  .fig .s  { font-size: 14px; fill: var(--md-default-fg-color--light, #555); }
  .fig .lane { font-size: 14px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .fig .edge { fill: none; stroke: var(--md-default-fg-color--light, #777); stroke-width: 1.5; }
  .fig .lbl { font-size: 14px; font-style: italic; fill: var(--md-default-fg-color--light, #555); }
  .fig .band { fill: rgba(120,144,156,0.08); stroke: rgba(120,144,156,0.45); stroke-width: 1; }
  .fig .band-ma { fill: rgba(63,81,181,0.06); stroke: rgba(63,81,181,0.45); stroke-width: 1; }
  .fig .band-ra { fill: rgba(0,137,123,0.06); stroke: rgba(0,137,123,0.45); stroke-width: 1; }
  .fig .n-sh { fill: var(--md-default-bg-color, #fff); stroke: %(SH)s; stroke-width: 1.4; }
  .fig .n-ma { fill: var(--md-default-bg-color, #fff); stroke: %(MA)s; stroke-width: 1.4; }
  .fig .n-ra { fill: var(--md-default-bg-color, #fff); stroke: %(RA)s; stroke-width: 1.4; }
  .fig .n-ma-hi { fill: rgba(63,81,181,0.14); stroke: %(MA)s; stroke-width: 2.6; }
  .fig .n-ra-hi { fill: rgba(0,137,123,0.14); stroke: %(RA)s; stroke-width: 2.6; }
  .fig .ma { fill: %(MA)s; }
  .fig .ra { fill: %(RA)s; }
</style>
""" % dict(MA=MA, RA=RA, SH=SH)

DEFS = """
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="var(--md-default-fg-color--light, #777)"/>
  </marker>
</defs>
"""

LH = 18  # line height in viewBox units


def node(x, y, w, h, lines, cls="n-sh", r=6):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" class="{cls}"/>']
    n = len(lines)
    y0 = y + h / 2 - (n - 1) * LH / 2 + 5
    for i, (txt, c) in enumerate(lines):
        out.append(f'<text x="{x + w / 2}" y="{y0 + i * LH:.1f}" text-anchor="middle" class="{c}">{txt}</text>')
    return "\n".join(out)


def edge(x1, y1, x2, y2, arrow=True, both=False, dashed=False):
    m = ' marker-end="url(#arr)"' if arrow else ""
    m += ' marker-start="url(#arr)"' if both else ""
    d = ' stroke-dasharray="5 4"' if dashed else ""
    return f'<path d="M{x1},{y1} L{x2},{y2}" class="edge"{m}{d}/>'


def poly(points, arrow=True, dashed=False):
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    m = ' marker-end="url(#arr)"' if arrow else ""
    s = ' stroke-dasharray="5 4"' if dashed else ""
    return f'<path d="{d}" class="edge"{m}{s}/>'


def label(x, y, txt, anchor="middle", cls="lbl"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{cls}">{txt}</text>'


# ---------------------------------------------------------------- Figure 1: lineage
def lineage():
    W = 1000
    p = [STYLE, DEFS]

    # root bar
    p.append(node(30, 16, W - 60, 48, [("MQTT three-layer stack  ·  Perception / Interaction / Control  ·  2025", "b")], "n-sh", r=8))

    nw, nh, gap = 146, 84, 12
    x0 = 34
    lane_h = nh + 60

    def lane(y, cls_band, cls_lane, title, nodes):
        p.append(f'<rect x="{x0 - 8}" y="{y}" width="{W - 2 * x0 + 16}" height="{lane_h}" rx="8" class="{cls_band}"/>')
        p.append(f'<text x="{x0 + 8}" y="{y + 22}" class="lane {cls_lane}">{title}</text>')
        ny = y + 38
        for i, (lines, cls) in enumerate(nodes):
            x = x0 + i * (nw + gap)
            p.append(node(x, ny, nw, nh, lines, cls))
            if i:
                p.append(edge(x - gap, ny + nh / 2, x, ny + nh / 2))
        return ny

    ma_nodes = [
        ([("LangGraph", "t"), ("multi-agent graph", "t"), ("2025", "s")], "n-ma"),
        ([("Per-agent LoRA", "t"), ("models via Ollama", "t"), ("Mar 2026", "s")], "n-ma"),
        ([("Multi-Agent,", "b"), ("Local", "b"), ("Apr 2026", "s")], "n-ma-hi"),
        ([("Visual memory", "t"), ("recall", "t"), ("Jun 2026", "s")], "n-ma"),
        ([("Multi-Agent,", "b"), ("Hybrid Cloud", "b"), ("forked 23 Jun 2026", "s")], "n-ma-hi"),
        ([("Merged pipeline,", "t"), ("cloud routing,", "t"), ("scene memory", "t"), ("Jun – Jul 2026", "s")], "n-ma"),
    ]
    ra_nodes = [
        ([("SoR-ReAct v2", "t"), ("demo deployments", "t"), ("2025", "s")], "n-ra"),
        ([("ReAct, Cloud", "b"), ("recording build", "t"), ("Jun 2026", "s")], "n-ra-hi"),
        ([("Singing pipeline,", "t"), ("song library", "t"), ("Jul 2026", "s")], "n-ra"),
        ([("Barge-in and", "t"), ("lip-sync recovery", "t"), ("Jul 2026", "s")], "n-ra"),
    ]

    y1 = 16 + 48 + 40
    ny1 = lane(y1, "band-ma", "ma", "Multi-agent family", ma_nodes)
    y2 = y1 + lane_h + 30
    ny2 = lane(y2, "band-ra", "ra", "ReAct family", ra_nodes)

    # arrows from root bar to first node of each lane
    p.append(edge(x0 + nw / 2, 64, x0 + nw / 2, ny1))
    # to ReAct lane: route down the left margin
    p.append(poly([(30, 40), (x0 - 18, 40), (x0 - 18, ny2 + nh / 2), (x0, ny2 + nh / 2)]))

    # time axis
    ay = y2 + lane_h + 30
    p.append(edge(x0 - 8, ay, W - x0 + 8, ay))
    p.append(label(x0 - 8, ay + 18, "earlier", "start"))
    p.append(label(W - x0 + 8, ay + 18, "later", "end"))
    p.append(label(W / 2, ay + 18, "Highlighted boxes are the three maintained versions. The two multi-agent versions share one code base.", "middle"))
    H = ay + 34
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Lineage of the Nadine platforms" class="fig" style="overflow:visible">')
    return "\n".join([svg] + p + ["</svg>"])


# ---------------------------------------------------------------- Figure 2: architecture
def architecture():
    W = 1000
    p = [STYLE, DEFS]
    nh = 46

    def band(y, h, title, nodes, cls="band"):
        p.append(f'<rect x="20" y="{y}" width="{W - 40}" height="{h}" rx="8" class="{cls}"/>')
        p.append(f'<text x="34" y="{y + 22}" class="lane">{title}</text>')
        total = sum(w for _, w in nodes) + 34 * (len(nodes) - 1)
        x = (W - total) / 2
        yy = y + 38
        for i, (txt, w) in enumerate(nodes):
            p.append(node(x, yy, w, nh, [(txt, "t")], "n-sh"))
            if i < len(nodes) - 1:
                p.append(edge(x + w, yy + nh / 2, x + w + 34, yy + nh / 2))
            x += w + 34

    # perception
    py, ph = 16, 118
    band(py, ph, "Perception layer · shared",
         [("RealSense RGB-D camera", 230), ("YOLOv8 face tracking · InsightFace recognition*", 400), ("Identity, 3D position, frames", 260)])
    p.append(label(W - 34, py + ph - 10, "* recognition and selective visual memory in the multi-agent versions only; the ReAct build tracks the closest face for gaze", "end"))

    # interaction
    iy = py + ph + 44
    step = 66
    panel_h = 40 + 8 * step + 30
    ih = panel_h + 50
    p.append(f'<rect x="20" y="{iy}" width="{W - 40}" height="{ih}" rx="8" class="band"/>')
    p.append(f'<text x="34" y="{iy + 22}" class="lane">Interaction layer · differs by family</text>')

    # --- multi-agent panel
    mx, my, mw, mh = 34, iy + 36, 560, panel_h
    p.append(f'<rect x="{mx}" y="{my}" width="{mw}" height="{mh}" rx="8" class="band-ma"/>')
    p.append(f'<text x="{mx + 16}" y="{my + 24}" class="lane ma">Multi-agent graph · LangGraph</text>')
    p.append(f'<text x="{mx + 16}" y="{my + 44}" class="s">Multi-Agent, Local  ·  Multi-Agent, Hybrid Cloud</text>')

    cx = mx + 180          # main column centre
    cw = 230               # main column node width
    y = my + 62
    col = ["Google STT", "Intent classifier", "Affective appraisal · PAD", "Orchestrator", "Memory retrieval"]
    ys = {}
    for name in col:
        p.append(node(cx - cw / 2, y, cw, nh, [(name, "t")], "n-ma"))
        ys[name] = y
        y += step
    for a, b in zip(col, col[1:]):
        p.append(edge(cx, ys[a] + nh, cx, ys[b]))
    # dashed outline: nodes merged into one turn-understanding call in the hybrid version
    ox, oy = cx - cw / 2 - 10, ys["Intent classifier"] - 10
    p.append(f'<rect x="{ox}" y="{oy}" width="{cw + 20}" height="{ys["Orchestrator"] + nh - oy + 10}" rx="8" '
             f'fill="none" stroke="{MA}" stroke-width="1.4" stroke-dasharray="6 4"/>')
    lx0 = ox + cw + 20 + 12
    p.append(label(lx0, ys["Affective appraisal · PAD"] + 12, "Merged into one", "start", "s"))
    p.append(label(lx0, ys["Affective appraisal · PAD"] + 30, "turn-understanding call", "start", "s"))
    p.append(label(lx0, ys["Affective appraisal · PAD"] + 48, "in Hybrid Cloud", "start", "s"))
    # tools row
    tools = [("Search", 90), ("Vision", 90), ("Knowledge RAG", 124)]
    tw = sum(w for _, w in tools) + 12 * 2
    tx = cx - tw / 2
    ty = y
    tcx = []
    for txt, w in tools:
        p.append(node(tx, ty, w, nh, [(txt, "t")], "n-ma"))
        c = tx + w / 2
        tcx.append(c)
        p.append(edge(cx, ys["Memory retrieval"] + nh, c, ty))
        tx += w + 12
    y += step
    p.append(node(cx - cw / 2, y, cw, nh, [("Response agent", "t")], "n-ma"))
    ry = y
    for c in tcx:
        p.append(edge(c, ty + nh, cx, ry))
    y += step
    p.append(node(cx - cw / 2, y, cw, nh, [("Memory update", "t")], "n-ma"))
    p.append(edge(cx, ry + nh, cx, y))
    uy = y

    # memory store on the right of the column
    sx, sw = mx + mw - 16 - 176, 176
    sy = (ys["Memory retrieval"] + uy) / 2 + 22
    p.append(node(sx, sy, sw, 92, [("Memory stores", "b"), ("text · episodic", "s"), ("visual scenes", "s"), ("ChromaDB · CLIP", "s")], "n-ma"))
    p.append(poly([(sx, sy + 20), (sx - 14, sy + 24), (sx - 14, ys["Memory retrieval"] + nh / 2), (cx + cw / 2, ys["Memory retrieval"] + nh / 2)], dashed=True))
    p.append(poly([(cx + cw / 2, uy + nh / 2), (sx - 14, uy + nh / 2), (sx - 14, sy + 68), (sx, sy + 68)], dashed=True))
    nx = (cx + cw / 2 + mx + mw) / 2
    p.append(label(nx, ys["Google STT"] + 30, "Every node is a separately", "middle"))
    p.append(label(nx, ys["Google STT"] + 48, "replaceable model. Intent,", "middle"))
    p.append(label(nx, ys["Google STT"] + 66, "affect and orchestration run", "middle"))
    p.append(label(nx, ys["Google STT"] + 84, "on local fine-tuned models.", "middle"))

    # --- ReAct panel
    rx_, ry_, rw_, rh_ = mx + mw + 14, my, W - 34 - (mx + mw + 14), mh
    p.append(f'<rect x="{rx_}" y="{ry_}" width="{rw_}" height="{rh_}" rx="8" class="band-ra"/>')
    p.append(f'<text x="{rx_ + 16}" y="{ry_ + 24}" class="lane ra">ReAct agent · LangChain</text>')
    p.append(f'<text x="{rx_ + 16}" y="{ry_ + 44}" class="s">ReAct, Cloud</text>')
    rcx = rx_ + rw_ / 2
    y0 = ry_ + 62
    p.append(node(rcx - cw / 2, y0, cw, nh, [("Google STT", "t")], "n-ra"))
    y1 = y0 + step
    p.append(edge(rcx, y0 + nh, rcx, y1))
    p.append(node(rcx - cw / 2, y1, cw, nh, [("Contextualizer · chat history", "t")], "n-ra"))
    # retrieval pair
    y2 = y1 + step
    pw = 160
    lx = rcx - pw - 6
    hx = rcx + 6
    p.append(node(lx, y2, pw, 62, [("Long-term memory", "b"), ("per-user · ChromaDB", "s")], "n-ra"))
    p.append(node(hx, y2, pw, 62, [("Knowledge base", "b"), ("ChromaDB", "s")], "n-ra"))
    p.append(edge(rcx - 40, y1 + nh, lx + pw / 2, y2))
    p.append(edge(rcx + 40, y1 + nh, hx + pw / 2, y2))
    # react loop
    y3 = y2 + 62 + 22
    p.append(edge(lx + pw / 2, y2 + 62, rcx - 40, y3))
    p.append(edge(hx + pw / 2, y2 + 62, rcx + 40, y3))
    p.append(node(rcx - cw / 2, y3, cw, 62, [("ReAct reasoning loop", "b"), ("gpt-5.4-mini", "s")], "n-ra"))
    # tools and structured answer
    y4 = y3 + 62 + 30
    p.append(node(lx, y4, pw, 80, [("Fixed tool set", "b"), ("search · news", "s"), ("weather · language", "s"), ("behaviors · sing", "s")], "n-ra"))
    p.append(node(hx, y4, pw, 80, [("Structured answer", "b"), ("reply · category", "s"), ("emotion · intensity", "s"), ("cause", "s")], "n-ra"))
    p.append(edge(rcx - 40, y3 + 62, lx + pw / 2, y4, both=True))
    p.append(edge(rcx + 40, y3 + 62, hx + pw / 2, y4))
    ny = y4 + 80 + 34
    p.append(label(rcx, ny, "Retrieval feeds one reasoning loop;", "middle"))
    p.append(label(rcx, ny + 18, "adding a capability adds a tool.", "middle"))
    p.append(label(rcx, ny + 46, "Emotion is appraised per turn;", "middle"))
    p.append(label(rcx, ny + 64, "no persistent affect, no visual memory.", "middle"))

    # control
    cy, ch = iy + ih + 44, 100
    band(cy, ch, "Control layer · shared",
         [("Azure TTS", 200), ("Lip-sync and animation", 300), ("Joint control and gaze", 300)])

    # MQTT arrows between bands
    ax = 210
    p.append(edge(ax, py + ph, ax, iy))
    p.append(label(ax + 12, py + ph + 27, "MQTT  ·  user id, position, frames", "start"))
    p.append(edge(ax, iy + ih, ax, cy))
    p.append(label(ax + 12, iy + ih + 27, "MQTT  ·  speech text, emotion, behavior", "start"))

    H = cy + ch + 16
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Architecture comparison of the multi-agent and ReAct interaction layers" class="fig" style="overflow:visible">')
    return "\n".join([svg] + p + ["</svg>"])


# ---------------------------------------------------------------- Figure 3: multi-agent graph (nadine_local)
def agent_graph():
    W = 1000
    p = [STYLE, DEFS]
    cx, cw, nh = 430, 240, 52

    def pill(y, txt):
        p.append(f'<rect x="{cx - 50}" y="{y}" width="100" height="34" rx="17" class="n-sh"/>')
        p.append(f'<text x="{cx}" y="{y + 22}" text-anchor="middle" class="b">{txt}</text>')

    def col(y, title, fn):
        p.append(node(cx - cw / 2, y, cw, nh, [(title, "t"), (fn, "s")], "n-ma"))

    def elabel(x, y, txt, anchor="start"):
        p.append(label(x, y, txt, anchor))

    ys = dict(start=20, ic=92, mr=176, aa=260, orc=344, tools=436, ra=530, au=614, end=706)
    pill(ys["start"], "START")
    col(ys["ic"], "Intent classifier", "intention_classifier")
    col(ys["mr"], "Memory retrieval", "memory_retrieve_agent")
    col(ys["aa"], "Affective appraisal", "affective_appraisal")
    col(ys["orc"], "Orchestrator", "orchestrator")
    tools = [("Search", "search_agent", 150), ("Vision", "vision_agent", 150), ("Knowledge RAG", "knowledge_rag_agent", 170)]
    tw = sum(w for _, _, w in tools) + 16 * 2
    tx = cx - tw / 2
    tcx = []
    for t, fn, w in tools:
        p.append(node(tx, ys["tools"], w, nh, [(t, "t"), (fn, "s")], "n-ma"))
        tcx.append((tx + w / 2, tx, tx + w))
        tx += w + 16
    col(ys["ra"], "Response agent", "response_agent")
    col(ys["au"], "Affective update", "affective_update")
    pill(ys["end"], "END")
    # memory update on the right
    mx, my, mw = 730, ys["orc"], 230
    p.append(node(mx, my, mw, nh, [("Memory update", "t"), ("memory_update_agent", "s")], "n-ma"))
    mcx = mx + mw / 2

    # main column edges
    p.append(edge(cx, ys["start"] + 34, cx, ys["ic"]))
    p.append(edge(cx, ys["ic"] + nh, cx, ys["mr"]))
    elabel(cx + 8, ys["ic"] + nh + 22, "otherwise")
    p.append(edge(cx, ys["mr"] + nh, cx, ys["aa"]))
    p.append(edge(cx, ys["aa"] + nh, cx, ys["orc"]))
    for c, x1, x2 in tcx:
        p.append(edge(cx, ys["orc"] + nh, c, ys["tools"]))
        p.append(edge(c, ys["tools"] + nh, cx, ys["ra"]))
    elabel(cx - cw / 2 - 8, ys["orc"] + nh + 26, "first plan step", "end")
    elabel(cx - cw / 2 - 8, ys["tools"] + nh + 26, "plan empty", "end")
    p.append(edge(cx, ys["ra"] + nh, cx, ys["au"]))
    p.append(edge(cx, ys["au"] + nh, cx, ys["end"]))
    elabel(cx + 8, ys["au"] + nh + 22, "otherwise")

    # tools -> orchestrator when plan steps remain (loop on the left)
    lx = tcx[0][1]
    p.append(poly([(lx, ys["tools"] + nh / 2), (150, ys["tools"] + nh / 2), (150, ys["orc"] + nh / 2), (cx - cw / 2, ys["orc"] + nh / 2)]))
    elabel(142, ys["tools"] - 6, "plan steps", "end")
    elabel(142, ys["tools"] + 12, "remaining", "end")

    # orchestrator -> response agent when no plan
    p.append(poly([(cx + cw / 2, ys["orc"] + nh / 2), (640, ys["orc"] + nh / 2), (640, ys["ra"] + nh / 2 - 8), (cx + cw / 2, ys["ra"] + nh / 2 - 8)]))
    elabel(648, ys["orc"] + nh / 2 + 44, "no plan")

    # intent classifier -> memory update (update_user_info)
    p.append(poly([(cx + cw / 2, ys["ic"] + nh / 2), (mcx, ys["ic"] + nh / 2), (mcx, my)]))
    elabel(cx + cw / 2 + 12, ys["ic"] + nh / 2 - 8, "update_user_info")
    # memory update -> memory retrieval (otherwise)
    p.append(poly([(mx, my + 14), (690, my + 14), (690, ys["mr"] + nh / 2 + 8), (cx + cw / 2, ys["mr"] + nh / 2 + 8)]))
    elabel(698, ys["mr"] + nh / 2 + 4, "otherwise")
    # memory update -> response agent (name confirmation pending)
    p.append(poly([(mcx - 40, my + nh), (mcx - 40, ys["ra"] + nh / 2 + 8), (cx + cw / 2, ys["ra"] + nh / 2 + 8)]))
    elabel(mcx - 32, ys["ra"] + nh / 2 - 6, "name confirmation")
    # memory update -> END (end_conversation, after the final save)
    p.append(poly([(mcx + 40, my + nh), (mcx + 40, ys["end"] + 17), (cx + 50, ys["end"] + 17)]))
    elabel(mcx + 48, ys["end"] - 30, "end_conversation,")
    elabel(mcx + 48, ys["end"] - 12, "after final save")
    # affective update -> memory update (end_conversation)
    p.append(poly([(cx + cw / 2, ys["au"] + 14), (mcx + 40 - 60, ys["au"] + 14)]))
    p.append(poly([(mcx - 20, ys["au"] + 14), (mcx - 20, my + nh + 1)], arrow=True))
    elabel(cx + cw / 2 + 12, ys["au"] + 8, "end_conversation")

    H = ys["end"] + 60
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="LangGraph multi-agent graph of the local platform" class="fig" style="overflow:visible">')
    return "\n".join([svg] + p + ["</svg>"])


if __name__ == "__main__":
    (OUT / "platforms_lineage.svg").write_text(lineage())
    (OUT / "platforms_architecture.svg").write_text(architecture())
    (OUT / "multiagent_graph.svg").write_text(agent_graph())
    print("written")
