from __future__ import annotations

import html
import math


FACTION_COLORS = {
    "Faction1": "#d1495b",
    "Faction2": "#edae49",
    "Faction3": "#00798c",
    "Faction4": "#30638e",
    None: "#d9d9d9",
}


def get_map_edges(regions):
    edges = set()

    for region_name, region_data in regions.items():
        for neighbor_name in region_data["neighbors"]:
            edge = tuple(sorted((region_name, neighbor_name)))
            edges.add(edge)

    return sorted(edges)


def find_universal_center(regions):
    region_count = len(regions)

    for region_name, region_data in regions.items():
        if len(region_data["neighbors"]) == region_count - 1:
            return region_name

    return None


def is_multi_ring_map(regions):
    names = set(regions)
    outer = {name for name in names if name.startswith("O")}
    middle = {name for name in names if name.startswith("M")}
    inner = {name for name in names if name.startswith("I")}
    return "C" in names and bool(outer) and bool(middle) and bool(inner)


def build_multi_ring_layout(regions, width, height):
    center_x = width / 2
    center_y = height / 2
    positions = {}

    ring_specs = [
        (sorted([name for name in regions if name.startswith("O")]), 320),
        (sorted([name for name in regions if name.startswith("M")]), 220),
        (sorted([name for name in regions if name.startswith("I")]), 120),
    ]

    for names, radius in ring_specs:
        if not names:
            continue
        for index, name in enumerate(names):
            angle = (2 * math.pi * index / len(names)) - (math.pi / 2)
            positions[name] = (
                center_x + (radius * math.cos(angle)),
                center_y + (radius * math.sin(angle)),
            )

    if "C" in regions:
        positions["C"] = (center_x, center_y)

    return positions


def build_ring_layout(regions, width, height, center_name):
    center_x = width / 2
    center_y = height / 2
    radius = min(width, height) * 0.34
    positions = {center_name: (center_x, center_y)}

    outer_names = sorted(name for name in regions if name != center_name)
    for index, name in enumerate(outer_names):
        angle = (2 * math.pi * index / len(outer_names)) - (math.pi / 2)
        positions[name] = (
            center_x + (radius * math.cos(angle)),
            center_y + (radius * math.sin(angle)),
        )

    return positions


def build_force_layout(regions, width, height, iterations=250):
    names = sorted(regions)
    count = len(names)
    center_x = width / 2
    center_y = height / 2
    radius = min(width, height) * 0.32
    positions = {}

    for index, name in enumerate(names):
        angle = (2 * math.pi * index / count) - (math.pi / 2)
        positions[name] = [
            center_x + (radius * math.cos(angle)),
            center_y + (radius * math.sin(angle)),
        ]

    edges = get_map_edges(regions)
    area = width * height
    ideal_distance = math.sqrt(area / max(count, 1)) * 0.35

    for _ in range(iterations):
        displacements = {name: [0.0, 0.0] for name in names}

        for index, first_name in enumerate(names):
            x1, y1 = positions[first_name]

            for second_name in names[index + 1:]:
                x2, y2 = positions[second_name]
                dx = x1 - x2
                dy = y1 - y2
                distance = math.hypot(dx, dy) or 0.01
                force = (ideal_distance * ideal_distance) / distance
                offset_x = (dx / distance) * force
                offset_y = (dy / distance) * force
                displacements[first_name][0] += offset_x
                displacements[first_name][1] += offset_y
                displacements[second_name][0] -= offset_x
                displacements[second_name][1] -= offset_y

        for first_name, second_name in edges:
            x1, y1 = positions[first_name]
            x2, y2 = positions[second_name]
            dx = x2 - x1
            dy = y2 - y1
            distance = math.hypot(dx, dy) or 0.01
            force = (distance * distance) / ideal_distance
            offset_x = (dx / distance) * force * 0.08
            offset_y = (dy / distance) * force * 0.08
            displacements[first_name][0] += offset_x
            displacements[first_name][1] += offset_y
            displacements[second_name][0] -= offset_x
            displacements[second_name][1] -= offset_y

        for name in names:
            x, y = positions[name]
            dx, dy = displacements[name]
            x += dx * 0.02
            y += dy * 0.02
            positions[name][0] = min(width - 50, max(50, x))
            positions[name][1] = min(height - 50, max(50, y))

    return {name: tuple(coords) for name, coords in positions.items()}


def build_map_layout(regions, width=900, height=900):
    if is_multi_ring_map(regions):
        return build_multi_ring_layout(regions, width, height)

    center_name = find_universal_center(regions)
    if center_name is not None:
        return build_ring_layout(regions, width, height, center_name)

    return build_force_layout(regions, width, height)


def clip_polygon_to_half_plane(polygon, normal_x, normal_y, threshold):
    clipped = []

    if not polygon:
        return clipped

    for index, current_point in enumerate(polygon):
        previous_point = polygon[index - 1]

        current_value = (current_point[0] * normal_x) + (current_point[1] * normal_y) - threshold
        previous_value = (previous_point[0] * normal_x) + (previous_point[1] * normal_y) - threshold

        current_inside = current_value >= -1e-6
        previous_inside = previous_value >= -1e-6

        if current_inside != previous_inside:
            dx = current_point[0] - previous_point[0]
            dy = current_point[1] - previous_point[1]
            denominator = (dx * normal_x) + (dy * normal_y)

            if abs(denominator) > 1e-9:
                t = (
                    threshold
                    - (previous_point[0] * normal_x)
                    - (previous_point[1] * normal_y)
                ) / denominator
                intersection = (
                    previous_point[0] + (t * dx),
                    previous_point[1] + (t * dy),
                )
                clipped.append(intersection)

        if current_inside:
            clipped.append(current_point)

    return clipped


def build_voronoi_cells(positions, width, height, padding=28):
    bounds = [
        (padding, padding),
        (width - padding, padding),
        (width - padding, height - padding),
        (padding, height - padding),
    ]
    cells = {}

    for region_name, (site_x, site_y) in positions.items():
        polygon = bounds[:]

        for other_name, (other_x, other_y) in positions.items():
            if other_name == region_name:
                continue

            normal_x = site_x - other_x
            normal_y = site_y - other_y
            threshold = (
                ((site_x * site_x) + (site_y * site_y))
                - ((other_x * other_x) + (other_y * other_y))
            ) / 2
            polygon = clip_polygon_to_half_plane(
                polygon,
                normal_x,
                normal_y,
                threshold,
            )

            if not polygon:
                break

        cells[region_name] = polygon

    return cells


def polygon_to_points_text(polygon):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in polygon)


def render_map_svg(map_name, map_definition, width=900, height=900):
    regions = map_definition["regions"]
    positions = build_map_layout(regions, width=width, height=height)
    cells = build_voronoi_cells(positions, width=width, height=height)
    svg_lines = []

    svg_lines.append(
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(map_name)} map'>"
    )

    for region_name in sorted(regions):
        region_data = regions[region_name]
        x, y = positions[region_name]
        fill = FACTION_COLORS.get(region_data["owner"], FACTION_COLORS[None])
        polygon = cells[region_name]
        points_text = polygon_to_points_text(polygon)
        svg_lines.append(
            f"<polygon points='{points_text}' fill='{fill}' class='territory' />"
        )
        svg_lines.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='6' class='anchor' />"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' class='label'>"
            f"{html.escape(region_name)}</text>"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y + 12:.1f}' text-anchor='middle' class='resource'>"
            f"R{region_data['resources']}</text>"
        )

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def render_map_html(map_name, map_definition):
    description = html.escape(map_definition["description"])
    regions = map_definition["regions"]
    svg = render_map_svg(map_name, map_definition)

    legend_items = []
    for faction_name in ["Faction1", "Faction2", "Faction3", "Faction4", None]:
        label = faction_name or "Unclaimed"
        color = FACTION_COLORS[faction_name]
        legend_items.append(
            f"<li><span class='swatch' style='background:{color}'></span>{html.escape(label)}</li>"
        )

    info_rows = []
    for region_name in sorted(regions):
        region_data = regions[region_name]
        neighbors = ", ".join(sorted(region_data["neighbors"]))
        owner = region_data["owner"] or "Unclaimed"
        info_rows.append(
            "<tr>"
            f"<td>{html.escape(region_name)}</td>"
            f"<td>{html.escape(owner)}</td>"
            f"<td>{region_data['resources']}</td>"
            f"<td>{len(region_data['neighbors'])}</td>"
            f"<td>{html.escape(neighbors)}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(map_name)} Visualization</title>
  <style>
    :root {{
      --bg: #f6f2e8;
      --ink: #1f2933;
      --panel: #fffdf8;
      --line: #b8b2a6;
      --grid: #e6dfd2;
    }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #f3ede0 0%, #faf7ef 100%);
      color: var(--ink);
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
    }}
    .lede {{
      margin: 0 0 20px;
      max-width: 70ch;
      line-height: 1.5;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
      gap: 20px;
      align-items: start;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--grid);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 10px 30px rgba(31, 41, 51, 0.08);
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
      background:
        radial-gradient(circle at center, rgba(255,255,255,0.78), rgba(255,255,255,0.35)),
        linear-gradient(180deg, rgba(233, 226, 210, 0.32), rgba(255, 255, 255, 0));
      border-radius: 14px;
    }}
    .territory {{
      stroke: #4b4138;
      stroke-width: 2.2;
      stroke-linejoin: round;
      opacity: 0.96;
    }}
    .anchor {{
      fill: rgba(31, 41, 51, 0.82);
    }}
    .label {{
      font-size: 15px;
      font-weight: 700;
      fill: #111827;
      pointer-events: none;
    }}
    .resource {{
      font-size: 11px;
      font-weight: 700;
      fill: #243b53;
      pointer-events: none;
      letter-spacing: 0.04em;
    }}
    .legend {{
      list-style: none;
      padding: 0;
      margin: 0 0 20px;
      display: grid;
      gap: 8px;
    }}
    .legend li {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .swatch {{
      width: 16px;
      height: 16px;
      border-radius: 999px;
      border: 1px solid #51463b;
      display: inline-block;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 8px 6px;
      border-bottom: 1px solid var(--grid);
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .note {{
      margin-top: 16px;
      font-size: 14px;
      line-height: 1.5;
    }}
    @media (max-width: 960px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>{html.escape(map_name)}</h1>
    <p class="lede">{description}</p>
    <div class="layout">
      <section class="card">
        {svg}
      </section>
      <aside class="card">
        <h2>Legend</h2>
        <ul class="legend">
          {"".join(legend_items)}
        </ul>
        <h2>Regions</h2>
        <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>Owner</th>
              <th>Res</th>
              <th>Links</th>
              <th>Neighbors</th>
            </tr>
          </thead>
          <tbody>
            {"".join(info_rows)}
          </tbody>
        </table>
        <p class="note">
          This view is intentionally lightweight and testing-oriented. It is meant to make
          connectivity and starting positions easy to inspect without committing to a final UI.
        </p>
      </aside>
    </div>
  </div>
</body>
</html>"""


def render_index_html(map_names):
    links = "\n".join(
        f"<li><a href='{html.escape(map_name)}.html'>{html.escape(map_name)}</a></li>"
        for map_name in map_names
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Map Visualizations</title>
  <style>
    body {{
      margin: 0;
      padding: 32px;
      font-family: Georgia, "Times New Roman", serif;
      background: #faf7ef;
      color: #1f2933;
    }}
    main {{
      max-width: 760px;
      margin: 0 auto;
      background: white;
      border: 1px solid #e6dfd2;
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 10px 30px rgba(31, 41, 51, 0.08);
    }}
    h1 {{
      margin-top: 0;
    }}
    li {{
      margin: 10px 0;
    }}
    a {{
      color: #30638e;
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Map Visualizations</h1>
    <p>Temporary testing views for inspecting region connectivity and starting positions.</p>
    <ul>
      {links}
    </ul>
  </main>
</body>
</html>"""
