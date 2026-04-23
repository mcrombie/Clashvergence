from __future__ import annotations

from pathlib import Path


MAP_GENERATOR_UI_OUTPUT = Path("reports/map_generator.html")


def render_map_generator_html() -> str:
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clashvergence Map Generator</title>
  <style>
    :root {
      --ink: #172026;
      --muted: #61717c;
      --line: #ccd5dc;
      --panel: #f7f9fb;
      --water: #d7ecf2;
      --land: #eef0df;
      --accent: #2c6f7c;
      --accent-2: #9b5f2e;
      --danger: #a33d45;
      --shadow: 0 12px 30px rgba(23, 32, 38, 0.12);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: #e8edf0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
    }
    aside {
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 22px;
      overflow-y: auto;
    }
    main {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-width: 0;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 24px;
      background: rgba(255,255,255,0.72);
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 24px;
      letter-spacing: 0;
    }
    h2 {
      margin: 28px 0 12px;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .lede {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .control {
      display: grid;
      gap: 7px;
      margin: 14px 0;
    }
    label {
      font-weight: 700;
      font-size: 13px;
    }
    input, select, button {
      font: inherit;
    }
    input[type="text"], input[type="number"], select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--ink);
      padding: 10px 11px;
    }
    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }
    .range-row {
      display: grid;
      grid-template-columns: 1fr 54px;
      align-items: center;
      gap: 10px;
    }
    .value {
      font-variant-numeric: tabular-nums;
      color: var(--muted);
      text-align: right;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }
    button {
      border: 1px solid var(--accent);
      border-radius: 7px;
      background: var(--accent);
      color: white;
      padding: 10px 13px;
      cursor: pointer;
      font-weight: 700;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
    }
    .preview-wrap {
      min-height: 0;
      padding: 18px 24px;
    }
    .preview {
      width: 100%;
      height: min(74vh, 820px);
      background: var(--water);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 8px;
      overflow: hidden;
    }
    svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .edge { stroke: rgba(35, 63, 70, 0.32); stroke-width: 1.4; }
    .sea { stroke: rgba(22, 92, 121, 0.48); stroke-width: 2.2; stroke-dasharray: 5 5; }
    .river { stroke: #367f9f; stroke-width: 3; stroke-linecap: round; opacity: 0.8; }
    .region { stroke: rgba(23,32,38,0.36); stroke-width: 1.2; }
    .start { stroke: #151515; stroke-width: 3; }
    .label { font-size: 9px; font-weight: 800; fill: rgba(23,32,38,0.75); pointer-events: none; }
    .footer {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
      gap: 18px;
      padding: 0 24px 22px;
    }
    .output, .stats {
      background: rgba(255,255,255,0.82);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-width: 0;
    }
    code {
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #183238;
      line-height: 1.45;
    }
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .stat strong {
      display: block;
      font-size: 20px;
      font-variant-numeric: tabular-nums;
    }
    .stat span {
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 980px) {
      .shell { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .footer { grid-template-columns: 1fr; }
      .preview { height: 58vh; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Map Generator</h1>
      <p class="lede">Tune geography, preview the world graph, then use the generated command to run a Clashvergence simulation.</p>

      <h2>World</h2>
      <div class="control">
        <label for="style">World Style</label>
        <select id="style">
          <option value="continent">Continent</option>
          <option value="frontier">Frontier</option>
          <option value="basin">Basin</option>
          <option value="archipelago">Archipelago</option>
          <option value="highlands">Highlands</option>
        </select>
      </div>
      <div class="control">
        <label for="seed">Seed</label>
        <input id="seed" type="text" value="world-aurora">
      </div>
      <div class="control">
        <label for="factions">Factions</label>
        <div class="range-row"><input id="factions" type="range" min="2" max="10" value="5"><span class="value" id="factions-value"></span></div>
      </div>
      <div class="control">
        <label for="regions">Regions</label>
        <div class="range-row"><input id="regions" type="range" min="24" max="96" value="56"><span class="value" id="regions-value"></span></div>
      </div>
      <div class="control">
        <label for="landmasses">Landmasses</label>
        <div class="range-row"><input id="landmasses" type="range" min="1" max="8" value="2"><span class="value" id="landmasses-value"></span></div>
      </div>

      <h2>Geography</h2>
      <div class="control">
        <label for="water">Water Level</label>
        <div class="range-row"><input id="water" type="range" min="0" max="0.9" step="0.01" value="0.34"><span class="value" id="water-value"></span></div>
      </div>
      <div class="control">
        <label for="rivers">Rivers</label>
        <div class="range-row"><input id="rivers" type="range" min="0" max="12" value="4"><span class="value" id="rivers-value"></span></div>
      </div>
      <div class="control">
        <label for="mountains">Mountain Spines</label>
        <div class="range-row"><input id="mountains" type="range" min="0" max="10" value="3"><span class="value" id="mountains-value"></span></div>
      </div>
      <div class="control">
        <label for="climate">Climate Mode</label>
        <select id="climate">
          <option value="varied">Varied</option>
          <option value="temperate">Temperate</option>
          <option value="arid">Arid</option>
          <option value="cold">Cold</option>
          <option value="tropical">Tropical</option>
        </select>
      </div>
      <div class="control">
        <label for="richness">Resource Richness</label>
        <div class="range-row"><input id="richness" type="range" min="0.45" max="1.8" step="0.01" value="1.05"><span class="value" id="richness-value"></span></div>
      </div>
      <div class="control">
        <label for="chokepoints">Chokepoint Density</label>
        <div class="range-row"><input id="chokepoints" type="range" min="0" max="1" step="0.01" value="0.52"><span class="value" id="chokepoints-value"></span></div>
      </div>
      <div class="control">
        <label for="diversity">Terrain Diversity</label>
        <div class="range-row"><input id="diversity" type="range" min="0" max="1" step="0.01" value="0.72"><span class="value" id="diversity-value"></span></div>
      </div>
      <div class="control">
        <label for="starts">Starting Placement</label>
        <select id="starts">
          <option value="balanced">Balanced</option>
          <option value="coastal">Coastal</option>
          <option value="heartland">Heartland</option>
          <option value="frontier">Frontier</option>
        </select>
      </div>
      <div class="actions">
        <button id="reroll" type="button">Reroll Seed</button>
        <button class="secondary" id="copy" type="button">Copy Command</button>
        <button class="secondary" id="export" type="button">Export JSON</button>
      </div>
    </aside>

    <main>
      <div class="topbar">
        <div>
          <strong id="title">Generated World</strong>
          <p class="lede" id="subtitle"></p>
        </div>
      </div>
      <div class="preview-wrap">
        <div class="preview" id="preview"></div>
      </div>
      <div class="footer">
        <div class="output"><code id="command"></code></div>
        <div class="stats"><div class="stat-grid" id="stats"></div></div>
      </div>
    </main>
  </div>

  <script>
    const controls = ["style","seed","factions","regions","landmasses","water","rivers","mountains","climate","richness","chokepoints","diversity","starts"];
    const colors = ["#d1495b","#edae49","#00798c","#30638e","#6a4c93","#2b9348","#ff7f51","#8d99ae","#8f5d2e","#417b5a"];
    let latestWorld = null;

    function hashString(value) {
      let h = 2166136261;
      for (let i = 0; i < value.length; i++) {
        h ^= value.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return h >>> 0;
    }

    function mulberry32(seed) {
      return function() {
        let t = seed += 0x6D2B79F5;
        t = Math.imul(t ^ t >>> 15, t | 1);
        t ^= t + Math.imul(t ^ t >>> 7, t | 61);
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      };
    }

    function val(id) {
      const el = document.getElementById(id);
      return el.type === "range" ? Number(el.value) : el.value;
    }

    function config() {
      return {
        style: val("style"),
        seed: val("seed") || "world",
        factions: val("factions"),
        regions: val("regions"),
        landmasses: val("landmasses"),
        water: val("water"),
        rivers: val("rivers"),
        mountains: val("mountains"),
        climate: val("climate"),
        richness: val("richness"),
        chokepoints: val("chokepoints"),
        diversity: val("diversity"),
        starts: val("starts")
      };
    }

    function distance(a, b) {
      return Math.hypot(a.x - b.x, a.y - b.y);
    }

    function addEdge(nodes, a, b, kind = "land") {
      if (a === b) return;
      const key = [a, b].sort((x, y) => x - y).join("-");
      if (nodes.edges.has(key)) return;
      nodes.edges.set(key, {a, b, kind});
      nodes.items[a].neighbors.push(b);
      nodes.items[b].neighbors.push(a);
    }

    function makeWorld(cfg) {
      const rng = mulberry32(hashString(JSON.stringify(cfg)));
      const landmasses = Math.max(1, Math.min(cfg.landmasses, Math.floor(cfg.regions / 8)));
      const sizes = Array.from({length: landmasses}, (_, i) => Math.max(4, Math.round(cfg.regions / landmasses * (0.82 + rng() * 0.36 + (i === 0 && cfg.style !== "archipelago" ? 0.28 : 0)))));
      while (sizes.reduce((a, b) => a + b, 0) > cfg.regions) sizes[sizes.indexOf(Math.max(...sizes))]--;
      while (sizes.reduce((a, b) => a + b, 0) < cfg.regions) sizes[sizes.indexOf(Math.min(...sizes))]++;
      const centers = [];
      for (let i = 0; i < landmasses; i++) {
        const angle = Math.PI * 2 * i / landmasses - Math.PI / 2;
        const radius = cfg.style === "archipelago" ? 0.29 : 0.21;
        centers.push({x: 0.5 + Math.cos(angle) * radius, y: 0.52 + Math.sin(angle) * radius * 0.78});
      }
      const nodes = {items: [], edges: new Map(), rivers: []};
      sizes.forEach((size, landmass) => {
        const center = centers[landmass];
        const scale = Math.sqrt(size / cfg.regions);
        for (let i = 0; i < size; i++) {
          const angle = Math.PI * 2 * i / size + (rng() - 0.5) * 0.35;
          const ring = Math.sqrt((i + 0.7) / size);
          const rx = (cfg.style === "archipelago" ? 0.19 : 0.35) * scale + 0.045;
          const ry = (cfg.style === "archipelago" ? 0.15 : 0.27) * scale + 0.04;
          const x = Math.min(0.95, Math.max(0.05, center.x + Math.cos(angle) * rx * ring * (0.86 + rng() * 0.32)));
          const y = Math.min(0.95, Math.max(0.05, center.y + Math.sin(angle) * ry * ring * (0.86 + rng() * 0.32)));
          nodes.items.push({id: nodes.items.length, name: `W${nodes.items.length + 1}`, x, y, landmass, neighbors: [], tags: [], climate: "temperate", resources: 2, owner: null});
        }
      });
      for (let landmass = 0; landmass < landmasses; landmass++) {
        const local = nodes.items.filter(n => n.landmass === landmass);
        for (const node of local) {
          const nearest = local.filter(n => n !== node).sort((a, b) => distance(node, a) - distance(node, b));
          nearest.slice(0, 2 + Math.round((1 - cfg.chokepoints) * 2)).forEach(n => addEdge(nodes, node.id, n.id));
        }
      }
      if (landmasses > 1) {
        for (let landmass = 0; landmass < landmasses; landmass++) {
          const next = (landmass + 1) % landmasses;
          const a = nodes.items.filter(n => n.landmass === landmass);
          const b = nodes.items.filter(n => n.landmass === next);
          let best = [a[0], b[0], Infinity];
          for (const first of a) for (const second of b) {
            const d = distance(first, second);
            if (d < best[2]) best = [first, second, d];
          }
          addEdge(nodes, best[0].id, best[1].id, "sea");
        }
      }
      const spines = Array.from({length: cfg.mountains}, () => {
        const angle = rng() * Math.PI * 2;
        const cx = 0.25 + rng() * 0.5;
        const cy = 0.25 + rng() * 0.5;
        const len = 0.25 + rng() * 0.5;
        return {x1: cx - Math.cos(angle) * len / 2, y1: cy - Math.sin(angle) * len / 2, x2: cx + Math.cos(angle) * len / 2, y2: cy + Math.sin(angle) * len / 2};
      });
      const elevation = (n) => {
        let best = 1;
        for (const s of spines) best = Math.min(best, pointLineDistance(n, s));
        return Math.max(0, 1 - best / 0.18);
      };
      const riverSources = [...nodes.items].sort((a, b) => elevation(b) - elevation(a)).slice(0, cfg.rivers);
      for (const source of riverSources) {
        const path = [source];
        let current = source;
        for (let i = 0; i < 9; i++) {
          const candidates = current.neighbors.map(id => nodes.items[id]).filter(n => !path.includes(n));
          if (!candidates.length) break;
          candidates.sort((a, b) => elevation(a) - elevation(b));
          current = candidates[0];
          path.push(current);
          if (current.x < 0.1 || current.y < 0.1 || current.x > 0.9 || current.y > 0.9) break;
        }
        if (path.length > 2) nodes.rivers.push(path.map(n => n.id));
      }
      const riverSet = new Set(nodes.rivers.flat());
      for (const n of nodes.items) {
        const coastal = n.x < 0.08 + cfg.water * 0.08 || n.y < 0.08 + cfg.water * 0.08 || n.x > 0.92 - cfg.water * 0.08 || n.y > 0.92 - cfg.water * 0.08 || cfg.style === "archipelago";
        const elev = elevation(n);
        const tags = [];
        if (coastal && rng() < 0.45 + cfg.water * 0.45) tags.push("coast");
        if (riverSet.has(n.id)) tags.push("riverland");
        if (elev > 0.75) tags.push("highland"); else if (elev > 0.5) tags.push("hills");
        const moist = (riverSet.has(n.id) ? 0.35 : 0) + (coastal ? 0.22 : 0) + rng() * cfg.diversity;
        if (moist > 0.78 && elev < 0.45) tags.push("marsh");
        else if (moist > 0.48 && elev < 0.68) tags.push("forest");
        else if (moist < 0.24) tags.push("steppe");
        else tags.push("plains");
        n.tags = [...new Set(tags)];
        n.resources = Math.max(1, Math.min(5, Math.round((2 + (n.tags.includes("riverland") ? 1 : 0) + (n.tags.includes("coast") ? 0.4 : 0) + (n.tags.includes("hills") ? 0.3 : 0)) * cfg.richness + rng() - 0.5)));
        n.climate = cfg.climate === "varied" ? (n.tags.includes("coast") ? "oceanic" : n.tags.includes("steppe") ? "steppe" : Math.abs(n.y - 0.5) > 0.38 ? "cold" : "temperate") : cfg.climate;
      }
      const starts = [];
      for (let i = 0; i < cfg.factions; i++) {
        const available = nodes.items.filter(n => !starts.includes(n));
        available.sort((a, b) => startScore(b, starts, cfg.starts) - startScore(a, starts, cfg.starts));
        const pick = available[0];
        pick.owner = i + 1;
        pick.resources = Math.max(3, pick.resources);
        starts.push(pick);
      }
      return nodes;
    }

    function pointLineDistance(p, s) {
      const dx = s.x2 - s.x1, dy = s.y2 - s.y1;
      const t = Math.max(0, Math.min(1, ((p.x - s.x1) * dx + (p.y - s.y1) * dy) / (dx * dx + dy * dy || 1)));
      return Math.hypot(p.x - (s.x1 + t * dx), p.y - (s.y1 + t * dy));
    }

    function startScore(n, starts, strategy) {
      let score = n.resources + n.neighbors.length * 0.2 + (n.tags.includes("riverland") ? 0.8 : 0);
      if (strategy === "coastal" && n.tags.includes("coast")) score += 2;
      if (strategy === "heartland" && !n.tags.includes("coast")) score += 1.3;
      if (strategy === "frontier" && n.neighbors.length <= 3) score += 1.3;
      if (starts.length) score += Math.min(...starts.map(s => distance(n, s))) * 12;
      return score;
    }

    function terrainColor(tags) {
      if (tags.includes("riverland")) return "#8ec9a6";
      if (tags.includes("marsh")) return "#80a887";
      if (tags.includes("highland")) return "#9b9b94";
      if (tags.includes("hills")) return "#b69c71";
      if (tags.includes("steppe")) return "#d6c270";
      if (tags.includes("forest")) return "#6aa06f";
      if (tags.includes("coast")) return "#d8c98e";
      return "#c8d37b";
    }

    function render() {
      const cfg = config();
      for (const id of controls) {
        const valueEl = document.getElementById(`${id}-value`);
        if (valueEl) valueEl.textContent = document.getElementById(id).value;
      }
      latestWorld = makeWorld(cfg);
      const width = 1000, height = 720;
      const lines = [`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Generated map preview">`];
      lines.push(`<rect width="${width}" height="${height}" fill="#d7ecf2"></rect>`);
      for (const edge of latestWorld.edges.values()) {
        const a = latestWorld.items[edge.a], b = latestWorld.items[edge.b];
        lines.push(`<line class="${edge.kind === "sea" ? "sea" : "edge"}" x1="${a.x * width}" y1="${a.y * height}" x2="${b.x * width}" y2="${b.y * height}"></line>`);
      }
      for (const path of latestWorld.rivers) {
        const points = path.map(id => `${latestWorld.items[id].x * width},${latestWorld.items[id].y * height}`).join(" ");
        lines.push(`<polyline class="river" points="${points}" fill="none"></polyline>`);
      }
      for (const n of latestWorld.items) {
        lines.push(`<circle class="region ${n.owner ? "start" : ""}" cx="${n.x * width}" cy="${n.y * height}" r="${n.owner ? 12 : 9}" fill="${n.owner ? colors[n.owner - 1] : terrainColor(n.tags)}"><title>${n.name}: ${n.tags.join(", ")} / ${n.climate} / R${n.resources}</title></circle>`);
        if (n.owner) lines.push(`<text class="label" x="${n.x * width}" y="${n.y * height - 16}" text-anchor="middle">F${n.owner}</text>`);
      }
      lines.push(`</svg>`);
      document.getElementById("preview").innerHTML = lines.join("");
      document.getElementById("title").textContent = `${cfg.style[0].toUpperCase() + cfg.style.slice(1)} World`;
      document.getElementById("subtitle").textContent = `${cfg.regions} regions, ${cfg.landmasses} landmass(es), ${cfg.factions} factions, seed ${cfg.seed}`;
      const command = `python main.py --map generated_world --num-factions ${cfg.factions} --turns 20 --map-style ${cfg.style} --map-seed "${cfg.seed}" --map-regions ${cfg.regions} --map-landmasses ${cfg.landmasses} --map-water ${cfg.water} --map-rivers ${cfg.rivers} --map-mountains ${cfg.mountains} --map-climate ${cfg.climate} --map-richness ${cfg.richness} --map-chokepoints ${cfg.chokepoints} --map-diversity ${cfg.diversity} --map-starts ${cfg.starts}`;
      document.getElementById("command").textContent = command;
      const coast = latestWorld.items.filter(n => n.tags.includes("coast")).length;
      const high = latestWorld.items.filter(n => n.tags.includes("highland") || n.tags.includes("hills")).length;
      const rivers = latestWorld.rivers.length;
      const avgDegree = latestWorld.items.reduce((sum, n) => sum + n.neighbors.length, 0) / latestWorld.items.length;
      document.getElementById("stats").innerHTML = [
        ["Coast", coast],
        ["Uplands", high],
        ["Rivers", rivers],
        ["Avg Degree", avgDegree.toFixed(1)]
      ].map(([label, value]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
    }

    for (const id of controls) document.getElementById(id).addEventListener("input", render);
    document.getElementById("reroll").addEventListener("click", () => {
      document.getElementById("seed").value = `world-${Math.random().toString(36).slice(2, 8)}`;
      render();
    });
    document.getElementById("copy").addEventListener("click", async () => {
      await navigator.clipboard.writeText(document.getElementById("command").textContent);
    });
    document.getElementById("export").addEventListener("click", () => {
      const payload = JSON.stringify({config: config(), preview: latestWorld}, null, 2);
      const blob = new Blob([payload], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "generated-map-preview.json";
      link.click();
      URL.revokeObjectURL(url);
    });
    render();
  </script>
</body>
</html>"""


def write_map_generator_html(output_path: Path = MAP_GENERATOR_UI_OUTPUT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_map_generator_html(), encoding="utf-8")
    return output_path
