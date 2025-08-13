import pandas as pd
import json

df = pd.read_csv("./processed/All_Passes_Combined_-_6_Games.csv")
completion_counts = (
    df[df["Turnover?"] == 0]
    .groupby(["Thrower", "Receiver"])
    .size()
    .reset_index(name="Completions")
)

# Prepare data for D3.js visualization
players = pd.unique(completion_counts[["Thrower", "Receiver"]].values.ravel("K"))
involvement = {p: 0 for p in players}

for _, r in completion_counts.iterrows():
    involvement[r["Thrower"]] += r["Completions"]
    involvement[r["Receiver"]] += r["Completions"]

# Create nodes data
nodes = [{"id": p, "group": 1, "size": involvement[p]} for p in players]

# Create links data
links = []
for _, r in completion_counts.iterrows():
    links.append({
        "source": r["Thrower"],
        "target": r["Receiver"], 
        "value": r["Completions"]
    })

# Create the HTML file with D3.js
html_content = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Pass Completion Network — Chemistry Selector</title>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    html, body {{ height: 100%; margin: 0; font-family: system-ui, Arial, sans-serif; background:#fff; }}
    #wrap {{ display:flex; flex-direction:column; height:100%; }}
    #toolbar {{
      display:flex; gap:12px; align-items:flex-start; padding:8px 12px;
      border-bottom:1px solid #eee; background:#fafafa; position:sticky; top:0; z-index:2;
      font-size:13px; flex-wrap: wrap;
    }}
    #network {{ flex:1 1 auto; }}
    .panel {{ display:flex; gap:8px; align-items:center; }}
    .col {{ display:flex; gap:6px; flex-direction:column; }}
    select[multiple] {{ min-width:220px; min-height:140px; padding:6px; }}
    label {{ user-select:none; }}
    .badge {{ background:#eee; border-radius:10px; padding:2px 8px; font-variant-numeric: tabular-nums; }}
    input[type="range"] {{ vertical-align: middle; }}
    .link {{ stroke: #9aa0a6; stroke-opacity: 0.7; }}
    .node {{ stroke: #fff; stroke-width: 1.5px; cursor: grab; }}
    .node:active {{ cursor: grabbing; }}
    .node-label {{ font-size: 12px; pointer-events: none; fill: #111; }}
    .tooltip {{
      position: absolute; background: rgba(0,0,0,0.85); color: #fff;
      padding: 6px 8px; border-radius: 4px; font-size: 12px; pointer-events: none;
    }}
    .muted {{ opacity: 0.08; }}
    .hidden {{ display:none; }}
  </style>
</head>
<body>
  <div id="wrap">
    <div id="toolbar">
      <div class="panel col">
        <strong>Players (multi‑select):</strong>
        <select id="playerMulti" multiple></select>
        <label><input id="includeExternal" type="checkbox"> Include external links (to/from selected)</label>
      </div>

      <div class="panel col">
        <strong>Mode</strong>
        <label><input type="radio" name="mode" value="all" checked> All</label>
        <label><input type="radio" name="mode" value="throws"> Throws</label>
        <label><input type="radio" name="mode" value="receives"> Receptions</label>
      </div>

      <div class="panel col">
        <label>Min completions:
          <input id="minVal" type="range" min="1" max="10" step="1" value="1">
        </label>
        <span id="minValLabel" class="badge">≥ 1</span>
        <label><input id="hideIsolated" type="checkbox"> Hide isolated nodes</label>
        <span id="stats" class="badge">0 links · 0 nodes</span>
      </div>
    </div>

    <div id="network"></div>
  </div>

  <script>
    // ===== Data from Python =====
    const data = {{
      nodes: {nodes_json},
      links: {links_json}
    }};

    // ===== Setup SVG =====
    const container = document.getElementById("network");
    let width = container.clientWidth, height = container.clientHeight;

    const svg = d3.select(container).append("svg")
      .attr("width", width).attr("height", height);

    const defs = svg.append("defs");
    defs.append("marker")
      .attr("id", "arrow").attr("viewBox", "0 -5 10 10")
      .attr("refX", 16).attr("refY", 0)
      .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
      .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#9aa0a6").attr("opacity", 0.9);

    const g = svg.append("g");

    // ===== Scales =====
    const sizeExtent = d3.extent(data.nodes, d => d.size || 0);
    const nodeSize = d3.scaleSqrt()
      .domain([Math.max(1, sizeExtent[0] || 1), Math.max(4, sizeExtent[1] || 4)])
      .range([10, 30]);

    const linkExtent = d3.extent(data.links, d => d.value || 0);
    const linkWidth = d3.scaleLinear()
      .domain([Math.max(1, linkExtent[0] || 1), Math.max(4, linkExtent[1] || 4)])
      .range([1.25, 6]);

    const color = d3.scaleOrdinal(d3.schemeTableau10);

    // ===== Force simulation =====
    const sim = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.links).id(d => d.id).distance(d => 140 - 10*Math.log1p(d.value || 1)).strength(0.3))
      .force("charge", d3.forceManyBody().strength(-250))
      .force("center", d3.forceCenter(width/2, height/2))
      .force("collide", d3.forceCollide().radius(d => nodeSize(d.size) + 4));

    // ===== Elements =====
    const link = g.append("g").attr("fill","none")
      .selectAll("path").data(data.links).join("path")
      .attr("class","link").attr("stroke-width", d => linkWidth(d.value))
      .attr("marker-end", "url(#arrow)");

    const linkHoverPts = g.append("g")
      .selectAll("circle").data(data.links).join("circle")
      .attr("r", 6).attr("opacity", 0);

    const node = g.append("g")
      .selectAll("circle").data(data.nodes).join("circle")
      .attr("class","node")
      .attr("r", d => nodeSize(d.size || 1))
      .attr("fill", d => color(d.group ?? 0))
      .call(drag(sim));

    const label = g.append("g")
      .selectAll("text").data(data.nodes).join("text")
      .attr("class","node-label").attr("text-anchor","middle").attr("dy",".35em")
      .text(d => d.id);

    // ===== Tooltip =====
    const tooltip = d3.select("body").append("div")
      .attr("class","tooltip").style("opacity", 0);

    node.on("mouseover", (event, d) => {{
      tooltip.style("opacity", 1).html(`<strong>${{d.id}}</strong><br/>Involvement: ${{d.size}}`);
    }}).on("mousemove", (event) => {{
      tooltip.style("left",(event.pageX+8)+"px").style("top",(event.pageY-24)+"px");
    }}).on("mouseout", () => tooltip.style("opacity", 0));

    linkHoverPts.on("mouseover", (event, d) => {{
      tooltip.style("opacity", 1).html(`${{d.source.id}} → ${{d.target.id}}<br/>Completions: ${{d.value}}`);
    }}).on("mousemove", (event) => {{
      tooltip.style("left",(event.pageX+8)+"px").style("top",(event.pageY-24)+"px");
    }}).on("mouseout", () => tooltip.style("opacity", 0));

    // ===== Zoom / pan =====
    svg.call(d3.zoom().scaleExtent([0.2, 4]).on("zoom", ev => g.attr("transform", ev.transform)));

    // ===== Curved links when reciprocal exists =====
    function linkArc(d) {{
      const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y, dr = Math.sqrt(dx*dx + dy*dy);
      const reciprocal = data.links.some(l => l !== d && l.source === d.target && l.target === d.source);
      return reciprocal ? `M${{d.source.x}},${{d.source.y}}A${{dr}},${{dr}} 0 0,1 ${{d.target.x}},${{d.target.y}}`
                        : `M${{d.source.x}},${{d.source.y}}L${{d.target.x}},${{d.target.y}}`;
    }}

    sim.on("tick", () => {{
      link.attr("d", linkArc);
      node.attr("cx", d => d.x).attr("cy", d => d.y);
      label.attr("x", d => d.x).attr("y", d => d.y);
      linkHoverPts.attr("cx", d => (d.source.x + d.target.x)/2)
                  .attr("cy", d => (d.source.y + d.target.y)/2);
    }});

    function drag(sim) {{
      function dragstarted(event) {{ if (!event.active) sim.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; }}
      function dragged(event) {{ event.subject.fx = event.x; event.subject.fy = event.y; }}
      function dragended(event) {{ if (!event.active) sim.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; }}
      return d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended);
    }}

    // ===== Controls =====
    const playerMulti = document.getElementById("playerMulti");
    const includeExternal = document.getElementById("includeExternal");
    const modeInputs = document.querySelectorAll('input[name="mode"]');
    const minSlider = document.getElementById("minVal");
    const minLabel = document.getElementById("minValLabel");
    const hideIsolated = document.getElementById("hideIsolated");
    const stats = document.getElementById("stats");

    // Populate multi-select with player names
    data.nodes.map(n => n.id).sort((a,b)=>a.localeCompare(b))
      .forEach(p => {{ const o = document.createElement("option"); o.value = p; o.textContent = p; playerMulti.appendChild(o); }});

    // Helpers to read selection into a Set
    function selectedPlayers() {{
      return new Set(Array.from(playerMulti.selectedOptions).map(o => o.value));
    }}

    // Edge visibility by selection & mode
    function edgeVisibleBySelection(edge, selSet, includeExternalFlag) {{
      if (selSet.size === 0) return true; // no selection = show all (then other filters apply)
      const inSelSource = selSet.has(edge.source.id);
      const inSelTarget = selSet.has(edge.target.id);
      // Pure chemistry: both ends selected
      if (!includeExternalFlag) return inSelSource && inSelTarget;
      // Include external: at least one endpoint selected
      return inSelSource || inSelTarget;
    }}

    function edgeVisibleByMode(edge, mode, selSet) {{
      if (mode === "throws")   return selSet.size === 0 ? true : selSet.has(edge.source.id) || selSet.has(edge.target.id);
      if (mode === "receives") return selSet.size === 0 ? true : selSet.has(edge.source.id) || selSet.has(edge.target.id);
      return true; // "all"
    }}

    // Update bindings for controls
    [playerMulti, includeExternal].forEach(el => el.addEventListener("change", update));
    modeInputs.forEach(r => r.addEventListener("change", update));
    minSlider.addEventListener("input", () => {{ minLabel.textContent = `≥ ${{minSlider.value}}`; update(); }});
    hideIsolated.addEventListener("change", update);

    function update() {{
      const selSet = selectedPlayers();
      const includeExt = includeExternal.checked;
      const mode = document.querySelector('input[name="mode"]:checked').value; // all|throws|receives
      const minV = +minSlider.value;

      // Show/hide links based on:
      // 1) min completions
      // 2) chemistry selection (pure or include external)
      // 3) mode (kept permissive; acts mainly on hover emphasis)
      link.classed("hidden", d => (d.value < minV) ||
        !edgeVisibleBySelection(d, selSet, includeExt) ||
        !edgeVisibleByMode(d, mode, selSet)
      );
      linkHoverPts.classed("hidden", d => (d.value < minV) ||
        !edgeVisibleBySelection(d, selSet, includeExt) ||
        !edgeVisibleByMode(d, mode, selSet)
      );

      // Visible link set for node isolation & hover emphasis
      const visibleLinks = data.links.filter(l => !link.filter(d => d === l).classed("hidden"));
      const incident = new Set(); visibleLinks.forEach(l => {{ incident.add(l.source.id); incident.add(l.target.id); }});

      // Hide isolated nodes (no incident visible link)
      node.classed("hidden", d => hideIsolated.checked && !incident.has(d.id));
      label.classed("hidden", d => hideIsolated.checked && !incident.has(d.id));

      // Stats
      const visEdgeCount = visibleLinks.length;
      const visNodeCount = hideIsolated.checked ? incident.size : data.nodes.length;
      stats.textContent = `${{visEdgeCount}} links · ${{visNodeCount}} nodes`;

      // Hover emphasis honoring selection/mode
      node.on("mouseover.filter", (event, d) => {{
        tooltip.style("opacity", 1).html(`<strong>${{d.id}}</strong><br/>Involvement: ${{d.size}}`);

        link.classed("muted", l => {{
          const hidden = link.filter(x => x === l).classed("hidden");
          if (hidden) return false;
          if (mode === "throws")   return l.source.id !== d.id;
          if (mode === "receives") return l.target.id !== d.id;
          return !(l.source.id === d.id || l.target.id === d.id);
        }});

        node.classed("muted", n => {{
          if (hideIsolated.checked && !incident.has(n.id)) return false;
          if (mode === "throws")
            return !(n.id === d.id || visibleLinks.some(l => l.source.id === d.id && l.target.id === n.id));
          if (mode === "receives")
            return !(n.id === d.id || visibleLinks.some(l => l.target.id === d.id && l.source.id === n.id));
          return !(n.id === d.id || visibleLinks.some(l =>
            (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)
          ));
        }});

        label.classed("muted", n => d3.select(node.nodes()[data.nodes.indexOf(n)]).classed("muted"));
      }}).on("mousemove.filter", (event) => {{
        tooltip.style("left",(event.pageX+8)+"px").style("top",(event.pageY-24)+"px");
      }}).on("mouseout.filter", () => {{
        tooltip.style("opacity", 0);
        link.classed("muted", false); node.classed("muted", false); label.classed("muted", false);
      }});
    }}

    // Initialize slider max + UI state
    const maxVal = d3.max(data.links, d => d.value) || 1;
    document.getElementById("minVal").max = Math.max(2, maxVal);
    document.getElementById("minVal").value = 1;
    document.getElementById("minValLabel").textContent = "≥ 1";
    update();

    // Resize
    window.addEventListener("resize", () => {{
      width = container.clientWidth; height = container.clientHeight;
      svg.attr("width", width).attr("height", height);
      sim.force("center", d3.forceCenter(width/2, height/2));
      sim.alpha(0.3).restart();
    }});
  </script>
</body>
</html>
""".format(nodes_json=json.dumps(nodes), links_json=json.dumps(links))

# Save the HTML file
with open("./processed/all_completions_network.html", "w") as f:
    f.write(html_content)

print("Interactive network visualization saved to ./processed/all_completions_network.html")
print("Open this file in your web browser to view the interactive network!")
print("Features:")
print("- Multi-player selection with chemistry analysis")
print("- Mode switching (All/Throws/Receptions)")
print("- Minimum completion filtering")
print("- Hide isolated nodes option")
print("- Real-time statistics")
print("- Enhanced hover emphasis based on selection")