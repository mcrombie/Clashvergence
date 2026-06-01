"""
Render a World Builder hex-map simulation as an animated GIF.
Generates a small random continent, runs 50 turns of Clashvergence,
and paints faction territory over the actual terrain hex grid.
"""
from __future__ import annotations

import json
import math
import random
import sys
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
SEED         = 42
MAP_W        = 80    # hex columns  ("Town" size)
MAP_H        = 56    # hex rows
HEX_SIZE_PX  = 7    # pixels per hex radius
NUM_FACTIONS = 4
NUM_TURNS    = 50
FPS          = 6
OUT_PATH     = Path("reports/hex_simulation.gif")

FACTION_COLORS_HEX = [
    "#d1495b", "#edae49", "#00798c", "#30638e",
    "#6a4c93", "#2b9348", "#ff7f51", "#8d99ae",
]

TERRAIN_COLORS_HEX = {
    "ocean":                 "#1a5c8a",
    "coast":                 "#4a9bb8",
    "grassland":             "#c8d878",
    "hills":                 "#a8a06a",
    "tundra_hills":          "#8cacb4",
    "desert_hills":          "#c8965a",
    "forest":                "#4a7c4e",
    "deep_forest":           "#2d5a32",
    "mountain":              "#8b8b8b",
    "tundra_mountain":       "#6a8c9c",
    "desert_mountain":       "#b87a50",
    "high_mountain":         "#d0d0d0",
    "tundra_high_mountain":  "#bcd0d8",
    "desert_high_mountain":  "#d8c4a0",
    "desert":                "#e8c878",
    "tundra":                "#a8b8b8",
    "wetland":               "#6a9b7c",
    "lake":                  "#6baed6",
    "highland":              "#b09060",
    "riverland":             "#7ab8a8",
    "plains":                "#d4c080",
    "mediterranean":         "#c4a85c",
}

# ─────────────────────────────────────────────────────────────────────────────
# Noise / mapgen (ported from mapgen.ts)
# ─────────────────────────────────────────────────────────────────────────────

def _hash(x, y, seed):
    n = math.sin(x * 127.1 + y * 311.7 + seed * 74.3) * 43758.5453123
    return n - math.floor(n)

def _smoothstep(t):
    return t * t * (3 - 2 * t)

def _snoise(x, y, seed):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    ux, uy = _smoothstep(fx), _smoothstep(fy)
    a = _hash(ix,   iy,   seed); b = _hash(ix+1, iy,   seed)
    c = _hash(ix,   iy+1, seed); d = _hash(ix+1, iy+1, seed)
    return (a*(1-ux) + b*ux)*(1-uy) + (c*(1-ux) + d*ux)*uy

def fbm(x, y, seed, octaves=6):
    v, amp, freq, norm = 0.0, 0.5, 1.0, 0.0
    for i in range(octaves):
        v    += _snoise(x*freq, y*freq, seed + i*17) * amp
        norm += amp; amp *= 0.5; freq *= 2
    return v / norm

def ridge_fbm(x, y, seed, octaves=5):
    v, amp, freq, norm = 0.0, 0.5, 1.0, 0.0
    for i in range(octaves):
        n = _snoise(x*freq, y*freq, seed + i*17)
        v    += (1 - abs(n*2 - 1)) * amp
        norm += amp; amp *= 0.5; freq *= 2
    return v / norm

def classify(elev, temp, moist, sea_level, highland_rate, alt_noise):
    if elev < sea_level: return "ocean"
    land = (elev - sea_level) / (1 - sea_level)
    if land < 0.07: return "coast"
    cold = temp < 0.22; hot = temp > 0.68
    dry  = moist < 0.35; wet = moist > 0.65; moist_ = moist > 0.42
    if land > 0.78:
        return "tundra_high_mountain" if cold else ("desert_high_mountain" if (hot and dry) else "high_mountain")
    if land > 0.55:
        return "tundra_mountain" if cold else ("desert_mountain" if (hot and dry) else "mountain")
    if cold:  return "tundra_hills" if land > 0.35 else "tundra"
    if hot and dry: return "desert_hills" if land > 0.35 else "desert"
    if land > 0.38 and alt_noise < highland_rate * 0.85: return "highland"
    if temp > 0.58 and 0.28 < moist < 0.52 and land < 0.45: return "mediterranean"
    if wet:   return "deep_forest" if land > 0.35 else "wetland"
    if moist_: return "forest" if land > 0.28 else "plains"
    if land > 0.32: return "hills"
    if moist < 0.30: return "grassland"
    return "plains"

def _mulberry32(seed):
    t = [seed & 0xFFFFFFFF]
    def rng():
        t[0] = (t[0] + 0x6D2B79F5) & 0xFFFFFFFF
        n = t[0] ^ (t[0] >> 15)
        n = (n * (n | 1)) & 0xFFFFFFFF
        n ^= (n + ((n ^ (n >> 7)) * (n | 61)) & 0xFFFFFFFF) & 0xFFFFFFFF
        return ((n ^ (n >> 14)) & 0xFFFFFFFF) / 0x100000000
    return rng

HEX_DIRS = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
SYLLABLES = ["ar","el","or","an","in","al","en","un","dar","vel","mor","tal",
             "sen","kar","fen","bor","ash","eth","orn","eld","val","mir","nor",
             "sur","gor","tor","har","var","kel","tel","ran","dan"]

def _make_name(rng):
    n = 2 if rng() < 0.45 else 3
    name = "".join(SYLLABLES[int(rng() * len(SYLLABLES))] for _ in range(n))
    return name[0].upper() + name[1:]

def hex_key(q, r): return f"{q},{r}"

def generate_world(width, height, seed,
                   sea_level=0.45, feature_scale=1.0, mountain_rate=0.35,
                   temperature=0.50, moisture=0.50, island_falloff=0.55,
                   erosion=0.20, polar_gradient=0.40, highland_rate=0.20,
                   num_regions=25):
    BASE = 3.5
    elev_map, alt_map = {}, {}

    for r in range(height):
        for col in range(width):
            q = col - r // 2
            k = hex_key(q, r)
            nx = (col / width)  * BASE * feature_scale
            ny = (r   / height) * BASE * feature_scale
            dx, dy = col/width - 0.5, r/height - 0.5
            dist = math.sqrt(dx*dx + dy*dy) * 2
            falloff = min(1, dist)**1.5 * island_falloff * 0.55
            base_e  = fbm(nx, ny, seed)
            ridge_e = ridge_fbm(nx*1.3, ny*1.3, seed+500)
            elev_map[k] = max(0, min(1, base_e*(1-mountain_rate*0.6) + ridge_e*mountain_rate*0.6 - falloff))
            alt_map[k]  = fbm(nx+300, ny+300, seed+4000, 3)

    # Erosion
    passes = round(erosion * 4)
    for _ in range(passes):
        smoothed = {}
        for r in range(height):
            for col in range(width):
                q = col - r // 2
                k = hex_key(q, r)
                s, cnt = elev_map[k] * 2, 2
                for dq, dr in HEX_DIRS:
                    nk = hex_key(q+dq, r+dr)
                    if nk in elev_map: s += elev_map[nk]; cnt += 1
                smoothed[k] = s / cnt
        elev_map.update(smoothed)

    hexes = {}
    for r in range(height):
        for col in range(width):
            q = col - r // 2
            k = hex_key(q, r)
            nx = (col/width) * BASE * feature_scale
            ny = (r/height)  * BASE * feature_scale
            land     = max(0, (elev_map[k]-sea_level)/(1-sea_level))
            elev_cool = (land-0.5)*0.6 if land > 0.5 else 0
            pole_cool = polar_gradient * abs(r/height-0.5)*2*0.65
            tn   = fbm(nx+100, ny+100, seed+2000, 4)
            temp = max(0, min(1, tn*0.5 + temperature*0.5 - elev_cool - pole_cool))
            mn   = fbm(nx+200, ny+200, seed+3000, 4)
            mst  = max(0, min(1, mn*0.6 + moisture*0.4))
            hexes[k] = {"q": q, "r": r,
                        "terrain": classify(elev_map[k], temp, mst, sea_level, highland_rate, alt_map[k])}

    # Region generation (farthest-point + BFS Voronoi)
    if num_regions > 0:
        rng = _mulberry32(seed ^ 0xDEADBEEF)
        land_hexes = [v for v in hexes.values() if v["terrain"] != "ocean"]
        n = min(num_regions, len(land_hexes))

        def dist2(a, b):
            dq, dr = a["q"]-b["q"], a["r"]-b["r"]
            return dq*dq + dr*dr + dq*dr

        seeds = [land_hexes[int(rng() * len(land_hexes))]]
        min_d = [dist2(h, seeds[0]) for h in land_hexes]
        while len(seeds) < n:
            best_idx = max(range(len(land_hexes)), key=lambda i: min_d[i])
            s = land_hexes[best_idx]; seeds.append(s)
            for i, h in enumerate(land_hexes):
                min_d[i] = min(min_d[i], dist2(h, s))

        assignment = {}
        queue = []
        for i, s in enumerate(seeds):
            k = hex_key(s["q"], s["r"])
            assignment[k] = i; queue.append((k, i))
        head = 0
        while head < len(queue):
            k, idx = queue[head]; head += 1
            h = hexes[k]
            for dq, dr in HEX_DIRS:
                nk = hex_key(h["q"]+dq, h["r"]+dr)
                if nk in hexes and nk not in assignment and hexes[nk]["terrain"] != "ocean":
                    assignment[nk] = idx; queue.append((nk, idx))

        regions = {}
        for i in range(n):
            regions[f"r{i}"] = {"name": _make_name(rng)}
        for k, idx in assignment.items():
            hexes[k]["region"] = f"r{idx}"

        return hexes, regions

    return hexes, {}

# ─────────────────────────────────────────────────────────────────────────────
# Generate map and translate to Clashvergence format
# ─────────────────────────────────────────────────────────────────────────────
print(f"Generating {MAP_W}×{MAP_H} hex world (seed={SEED})...")
random.seed(SEED)
hexes, regions_meta = generate_world(MAP_W, MAP_H, SEED, num_regions=25)

land_count = sum(1 for h in hexes.values() if h["terrain"] != "ocean")
region_count = len({h.get("region") for h in hexes.values() if h.get("region")})
print(f"  {len(hexes)} hexes, {land_count} land, {region_count} regions")

# Build a wwmap-compatible dict
wwmap_data = {
    "name": f"Generated World (seed {SEED})",
    "width": MAP_W,
    "height": MAP_H,
    "hexSize": HEX_SIZE_PX,
    "hexes": hexes,
    "rivers": {},
    "regions": {rid: {"name": rd["name"]} for rid, rd in regions_meta.items()},
}

# Write to temp file and translate
tmp_wwmap = Path(tempfile.mktemp(suffix=".wwmap"))
tmp_cmap  = tmp_wwmap.with_suffix(".cmap.json")
tmp_wwmap.write_text(json.dumps(wwmap_data), encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "typescript" / "worldwright"))
from wwmap_to_clashvergence import translate
map_def = translate(tmp_wwmap, num_factions=NUM_FACTIONS)
tmp_cmap.write_text(json.dumps(map_def, indent=2), encoding="utf-8")
print(f"  Translated: {len(map_def['regions'])} Clashvergence regions, "
      f"{len(map_def['sea_links'])} sea links")

# ─────────────────────────────────────────────────────────────────────────────
# Inject into Clashvergence and run simulation
# ─────────────────────────────────────────────────────────────────────────────
from main import _inject_map_file
map_name, _ = _inject_map_file(str(tmp_cmap))

from src.maps import MAPS
from src.world import create_world
from src.simulation import run_simulation

random.seed(SEED)
world = create_world(map_name=map_name, num_factions=NUM_FACTIONS)
print(f"Simulating {NUM_TURNS} turns...")
world = run_simulation(world, num_turns=NUM_TURNS, verbose=False)
print("  Done.")

# ─────────────────────────────────────────────────────────────────────────────
# Reconstruct ownership per turn
# ─────────────────────────────────────────────────────────────────────────────
initial_owners = {name: data["owner"] for name, data in map_def["regions"].items()}
current = dict(initial_owners)
ownership_by_turn = [dict(current)]

for turn in range(1, NUM_TURNS + 1):
    for ev in world.events:
        if ev.turn == turn - 1 and ev.region is not None:
            if ev.type == "expand":
                current[ev.region] = ev.faction
            elif ev.type == "attack" and ev.get("success", False):
                current[ev.region] = ev.faction
    ownership_by_turn.append(dict(current))

# Map generic FactionN → named faction key → color
faction_keys = list(world.factions.keys())
generic_to_named = {f"Faction{i+1}": k for i, k in enumerate(faction_keys)}
named_to_color   = {}
for i, (generic, named) in enumerate(generic_to_named.items()):
    named_to_color[named]   = FACTION_COLORS_HEX[i % len(FACTION_COLORS_HEX)]
    named_to_color[generic] = FACTION_COLORS_HEX[i % len(FACTION_COLORS_HEX)]  # fallback

# ─────────────────────────────────────────────────────────────────────────────
# Hex rendering helpers
# ─────────────────────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    sys.exit("pip install pillow")

def parse_hex_color(s):
    s = s.lstrip("#")
    return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16))

def blend(base, overlay, alpha=0.55):
    return tuple(int(b*(1-alpha) + o*alpha) for b, o in zip(base, overlay))

def hex_to_pixel(q, r, size):
    x = size * (math.sqrt(3)*q + math.sqrt(3)/2*r)
    y = size * (1.5*r)
    return x, y

def hex_corners(cx, cy, size):
    return [
        (cx + size*math.cos(math.radians(60*i - 30)),
         cy + size*math.sin(math.radians(60*i - 30)))
        for i in range(6)
    ]

# Compute canvas bounds
S = HEX_SIZE_PX
PAD = 10
all_px = [hex_to_pixel(h["q"], h["r"], S) for h in hexes.values()]
min_x = min(p[0] for p in all_px) - S - PAD
min_y = min(p[1] for p in all_px) - S - PAD
max_x = max(p[0] for p in all_px) + S + PAD
max_y = max(p[1] for p in all_px) + S + PAD
W     = int(max_x - min_x) + 1
H_img = int(max_y - min_y) + 1

# Pre-compute each region's pixel centroid (stable across frames)
region_px_centroid: dict[str, tuple[float, float]] = {}
region_hex_list: dict[str, list] = {}
for h in hexes.values():
    rid = h.get("region")
    if rid:
        region_hex_list.setdefault(rid, []).append(h)
for rid, hlist in region_hex_list.items():
    xs = [hex_to_pixel(h["q"], h["r"], S)[0] - min_x for h in hlist]
    ys = [hex_to_pixel(h["q"], h["r"], S)[1] - min_y for h in hlist]
    region_px_centroid[rid] = (sum(xs)/len(xs), sum(ys)/len(ys))

# Try to load a readable font; fall back to PIL default
try:
    font_label = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 13)
    font_turn  = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
except Exception:
    font_label = ImageFont.load_default()
    font_turn  = font_label

def draw_label(draw, text, cx, cy, text_color, bg_color, font):
    """Draw text centred at (cx, cy) with a filled pill background."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 5, 3
    x0 = cx - tw/2 - pad_x
    y0 = cy - th/2 - pad_y
    x1 = cx + tw/2 + pad_x
    y1 = cy + th/2 + pad_y
    draw.rounded_rectangle([x0, y0, x1, y1], radius=4, fill=bg_color)
    draw.text((cx - tw/2, cy - th/2), text, fill=text_color, font=font)

def render_frame(turn_idx):
    ownership = ownership_by_turn[turn_idx]
    region_owner = {
        r: generic_to_named.get(o, o)
        for r, o in ownership.items() if o
    }

    img  = Image.new("RGB", (W, H_img), (13, 17, 23))
    draw = ImageDraw.Draw(img)

    # Draw hexes
    for h in hexes.values():
        q, r    = h["q"], h["r"]
        terrain = h.get("terrain", "plains")
        region  = h.get("region")
        cx, cy  = hex_to_pixel(q, r, S)
        cx -= min_x; cy -= min_y
        corners  = hex_corners(cx, cy, S)
        base_rgb = parse_hex_color(TERRAIN_COLORS_HEX.get(terrain, "#888888"))
        owner    = region_owner.get(region) if region else None
        if owner and owner in named_to_color:
            fill = blend(base_rgb, parse_hex_color(named_to_color[owner]), alpha=0.52)
        else:
            fill = base_rgb
        draw.polygon(corners, fill=fill)
        if terrain != "ocean":
            draw.polygon(corners, outline=(0, 0, 0))

    # Compute per-faction territory centroid (weighted by hex count)
    faction_px: dict[str, list[tuple[float,float]]] = {}
    for rid, owner in region_owner.items():
        cx, cy = region_px_centroid.get(rid, (None, None))
        if cx is None: continue
        n = len(region_hex_list.get(rid, []))
        faction_px.setdefault(owner, [])
        faction_px[owner].extend([(cx, cy)] * n)  # weight by hex count

    # Draw faction name labels
    for owner, pts in faction_px.items():
        if not pts or owner not in named_to_color: continue
        lx = sum(p[0] for p in pts) / len(pts)
        ly = sum(p[1] for p in pts) / len(pts)
        color_rgb  = parse_hex_color(named_to_color[owner])
        # Darken the background slightly
        bg = tuple(max(0, c - 40) for c in color_rgb) + (210,)
        # Short name: first word only if long
        label = owner.split()[0] if len(owner) > 12 else owner
        draw_label(draw, label, lx, ly, (255,255,255), color_rgb, font_label)

    # Turn counter (top-left corner)
    turn_label = f"Turn {turn_idx}"
    draw_label(draw, turn_label, 48, 14, (255,255,255), (30,30,40), font_turn)

    return img

print(f"Rendering {len(ownership_by_turn)} frames...")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

frames = [render_frame(i) for i in range(len(ownership_by_turn))]
frames[0].save(
    str(OUT_PATH),
    save_all=True,
    append_images=frames[1:],
    duration=1000 // FPS,
    loop=0,
    optimize=False,
)

# Cleanup
tmp_wwmap.unlink(missing_ok=True)
tmp_cmap.unlink(missing_ok=True)

print(f"Done: {OUT_PATH.resolve()}")
