from __future__ import annotations

import html
import colorsys
import math
import re


FACTION_COLORS = {
    "Faction1": "#d1495b",
    "Faction2": "#edae49",
    "Faction3": "#00798c",
    "Faction4": "#30638e",
    None: "#d9d9d9",
}
FACTION_COLOR_SEQUENCE = [
    "#d1495b",
    "#edae49",
    "#00798c",
    "#30638e",
    "#6a4c93",
    "#2b9348",
    "#ff7f51",
    "#8d99ae",
]


def natural_sort_key(name):
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", name)
    if match:
        return (match.group(1), int(match.group(2)))
    return (name, -1)


def get_faction_index(faction_name):
    if faction_name is None:
        return None

    match = re.fullmatch(r"Faction(\d+)", faction_name)
    if match:
        return int(match.group(1))

    return None


def get_faction_color(faction_name):
    if faction_name in FACTION_COLORS:
        return FACTION_COLORS[faction_name]

    faction_index = get_faction_index(faction_name)
    if faction_index is None:
        return "#7f8c8d"

    sequence_index = faction_index - 1
    if sequence_index < len(FACTION_COLOR_SEQUENCE):
        return FACTION_COLOR_SEQUENCE[sequence_index]

    hue = ((sequence_index * 0.61803398875) % 1.0)
    saturation = 0.58
    value = 0.78
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return "#{:02x}{:02x}{:02x}".format(
        int(red * 255),
        int(green * 255),
        int(blue * 255),
    )


def get_present_factions(regions):
    faction_names = sorted(
        {region_data["owner"] for region_data in regions.values() if region_data["owner"] is not None},
        key=natural_sort_key,
    )
    return faction_names


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
    outer = {name for name in names if re.fullmatch(r"O\d+", name)}
    middle = {name for name in names if re.fullmatch(r"M\d+", name)}
    inner = {name for name in names if re.fullmatch(r"I\d+", name)}
    return "C" in names and bool(outer) and bool(middle) and bool(inner)


def is_ring_map(regions):
    center_name = find_universal_center(regions)
    if center_name is None:
        return False

    outer_names = [name for name in regions if name != center_name]
    return all(center_name in regions[name]["neighbors"] for name in outer_names)


def build_multi_ring_layout(regions, width, height):
    center_x = width / 2
    center_y = height / 2
    positions = {}

    ring_specs = [
        (sorted([name for name in regions if name.startswith("O")], key=natural_sort_key), 320),
        (sorted([name for name in regions if name.startswith("M")], key=natural_sort_key), 220),
        (sorted([name for name in regions if name.startswith("I")], key=natural_sort_key), 120),
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

    outer_names = sorted((name for name in regions if name != center_name), key=natural_sort_key)
    for index, name in enumerate(outer_names):
        angle = (2 * math.pi * index / len(outer_names)) - (math.pi / 2)
        positions[name] = (
            center_x + (radius * math.cos(angle)),
            center_y + (radius * math.sin(angle)),
        )

    return positions


def build_force_layout(regions, width, height, iterations=250):
    names = sorted(regions, key=natural_sort_key)
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


def polygon_to_points_text(polygon):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in polygon)


def polar_to_cartesian(center_x, center_y, radius, angle_deg):
    angle_rad = math.radians(angle_deg)
    return (
        center_x + (radius * math.cos(angle_rad)),
        center_y + (radius * math.sin(angle_rad)),
    )


def build_annular_sector(center_x, center_y, inner_radius, outer_radius, start_deg, end_deg, steps=8):
    polygon = []

    if outer_radius > 0:
        for step in range(steps + 1):
            angle = start_deg + ((end_deg - start_deg) * step / steps)
            polygon.append(polar_to_cartesian(center_x, center_y, outer_radius, angle))

    if inner_radius <= 0:
        polygon.append((center_x, center_y))
        return polygon

    for step in range(steps, -1, -1):
        angle = start_deg + ((end_deg - start_deg) * step / steps)
        polygon.append(polar_to_cartesian(center_x, center_y, inner_radius, angle))

    return polygon


def get_annular_label_position(center_x, center_y, inner_radius, outer_radius, start_deg, end_deg):
    angle = (start_deg + end_deg) / 2
    radius = (inner_radius + outer_radius) / 2
    return polar_to_cartesian(center_x, center_y, radius, angle)


def render_graph_map_svg(map_name, map_definition, width=900, height=900):
    regions = map_definition["regions"]
    positions = build_map_layout(regions, width=width, height=height)
    edges = get_map_edges(regions)
    svg_lines = []

    svg_lines.append(
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(map_name)} map'>"
    )

    for first_name, second_name in edges:
        x1, y1 = positions[first_name]
        x2, y2 = positions[second_name]
        svg_lines.append(
            f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' class='edge' />"
        )

    for region_name in sorted(regions, key=natural_sort_key):
        region_data = regions[region_name]
        x, y = positions[region_name]
        fill = get_faction_color(region_data["owner"])
        svg_lines.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='24' fill='{fill}' class='node' />"
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


def render_ring_map_svg(map_name, map_definition, width=900, height=900):
    regions = map_definition["regions"]
    center_name = find_universal_center(regions)
    outer_names = sorted((name for name in regions if name != center_name), key=natural_sort_key)
    center_x = width / 2
    center_y = height / 2
    center_radius = min(width, height) * 0.16
    outer_radius = min(width, height) * 0.47
    sector_width = 360 / len(outer_names)
    first_start = -90 - (sector_width / 2)
    svg_lines = []

    svg_lines.append(
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(map_name)} map'>"
    )

    center_fill = get_faction_color(regions[center_name]["owner"])
    center_polygon = build_annular_sector(
        center_x,
        center_y,
        0,
        center_radius,
        0,
        360,
        steps=32,
    )
    svg_lines.append(
        f"<polygon points='{polygon_to_points_text(center_polygon)}' fill='{center_fill}' class='territory' />"
    )
    svg_lines.append(
        f"<text x='{center_x:.1f}' y='{center_y - 8:.1f}' text-anchor='middle' class='label'>{html.escape(center_name)}</text>"
    )
    svg_lines.append(
        f"<text x='{center_x:.1f}' y='{center_y + 12:.1f}' text-anchor='middle' class='resource'>R{regions[center_name]['resources']}</text>"
    )

    for index, region_name in enumerate(outer_names):
        start_deg = first_start + (index * sector_width)
        end_deg = start_deg + sector_width
        polygon = build_annular_sector(
            center_x,
            center_y,
            center_radius,
            outer_radius,
            start_deg,
            end_deg,
        )
        x, y = get_annular_label_position(
            center_x,
            center_y,
            center_radius,
            outer_radius,
            start_deg,
            end_deg,
        )
        fill = get_faction_color(regions[region_name]["owner"])
        svg_lines.append(
            f"<polygon points='{polygon_to_points_text(polygon)}' fill='{fill}' class='territory' />"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' class='label'>{html.escape(region_name)}</text>"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y + 12:.1f}' text-anchor='middle' class='resource'>R{regions[region_name]['resources']}</text>"
        )

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def render_multi_ring_map_svg(map_name, map_definition, width=900, height=900):
    regions = map_definition["regions"]
    center_x = width / 2
    center_y = height / 2
    inner_center_radius = 70
    inner_outer_radius = 170
    middle_outer_radius = 290
    outer_outer_radius = 410
    svg_lines = []

    svg_lines.append(
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{html.escape(map_name)} map'>"
    )

    center_polygon = build_annular_sector(
        center_x,
        center_y,
        0,
        inner_center_radius,
        0,
        360,
        steps=32,
    )
    center_fill = get_faction_color(regions["C"]["owner"])
    svg_lines.append(
        f"<polygon points='{polygon_to_points_text(center_polygon)}' fill='{center_fill}' class='territory' />"
    )
    svg_lines.append(
        f"<text x='{center_x:.1f}' y='{center_y - 8:.1f}' text-anchor='middle' class='label'>C</text>"
    )
    svg_lines.append(
        f"<text x='{center_x:.1f}' y='{center_y + 12:.1f}' text-anchor='middle' class='resource'>R{regions['C']['resources']}</text>"
    )

    outer_names = sorted((name for name in regions if name.startswith("O")), key=natural_sort_key)
    middle_names = sorted((name for name in regions if name.startswith("M")), key=natural_sort_key)
    inner_names = sorted((name for name in regions if name.startswith("I")), key=natural_sort_key)

    outer_step = 360 / len(outer_names)
    middle_step = 360 / len(middle_names)
    inner_step = 360 / len(inner_names)

    for index, region_name in enumerate(outer_names):
        start_deg = (-90 - (outer_step / 2)) + (index * outer_step)
        end_deg = start_deg + outer_step
        polygon = build_annular_sector(
            center_x,
            center_y,
            middle_outer_radius,
            outer_outer_radius,
            start_deg,
            end_deg,
        )
        x, y = get_annular_label_position(
            center_x,
            center_y,
            middle_outer_radius,
            outer_outer_radius,
            start_deg,
            end_deg,
        )
        fill = get_faction_color(regions[region_name]["owner"])
        svg_lines.append(
            f"<polygon points='{polygon_to_points_text(polygon)}' fill='{fill}' class='territory' />"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' class='label'>{html.escape(region_name)}</text>"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y + 12:.1f}' text-anchor='middle' class='resource'>R{regions[region_name]['resources']}</text>"
        )

    for index, region_name in enumerate(middle_names):
        start_deg = -90 + (index * middle_step)
        end_deg = start_deg + middle_step
        polygon = build_annular_sector(
            center_x,
            center_y,
            inner_outer_radius,
            middle_outer_radius,
            start_deg,
            end_deg,
        )
        x, y = get_annular_label_position(
            center_x,
            center_y,
            inner_outer_radius,
            middle_outer_radius,
            start_deg,
            end_deg,
        )
        fill = get_faction_color(regions[region_name]["owner"])
        svg_lines.append(
            f"<polygon points='{polygon_to_points_text(polygon)}' fill='{fill}' class='territory' />"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' class='label'>{html.escape(region_name)}</text>"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y + 12:.1f}' text-anchor='middle' class='resource'>R{regions[region_name]['resources']}</text>"
        )

    for index, region_name in enumerate(inner_names):
        start_deg = -90 + (index * inner_step)
        end_deg = start_deg + inner_step
        polygon = build_annular_sector(
            center_x,
            center_y,
            inner_center_radius,
            inner_outer_radius,
            start_deg,
            end_deg,
        )
        x, y = get_annular_label_position(
            center_x,
            center_y,
            inner_center_radius,
            inner_outer_radius,
            start_deg,
            end_deg,
        )
        fill = get_faction_color(regions[region_name]["owner"])
        svg_lines.append(
            f"<polygon points='{polygon_to_points_text(polygon)}' fill='{fill}' class='territory' />"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y - 8:.1f}' text-anchor='middle' class='label'>{html.escape(region_name)}</text>"
        )
        svg_lines.append(
            f"<text x='{x:.1f}' y='{y + 12:.1f}' text-anchor='middle' class='resource'>R{regions[region_name]['resources']}</text>"
        )

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def render_map_svg(map_name, map_definition, width=900, height=900):
    regions = map_definition["regions"]

    if is_multi_ring_map(regions):
        return render_multi_ring_map_svg(map_name, map_definition, width=width, height=height)

    if is_ring_map(regions):
        return render_ring_map_svg(map_name, map_definition, width=width, height=height)

    return render_graph_map_svg(map_name, map_definition, width=width, height=height)


def supports_exact_border_view(regions):
    return is_ring_map(regions) and not is_multi_ring_map(regions)


def render_map_html(map_name, map_definition):
    description = html.escape(map_definition["description"])
    regions = map_definition["regions"]
    graph_svg = render_graph_map_svg(map_name, map_definition)
    has_exact_border_view = supports_exact_border_view(regions)
    border_svg = render_map_svg(map_name, map_definition) if has_exact_border_view else graph_svg

    legend_items = []
    for faction_name in [*get_present_factions(regions), None]:
        label = faction_name or "Unclaimed"
        color = get_faction_color(faction_name)
        legend_items.append(
            f"<li><span class='swatch' style='background:{color}'></span>{html.escape(label)}</li>"
        )

    info_rows = []
    for region_name in sorted(regions, key=natural_sort_key):
        region_data = regions[region_name]
        neighbors = ", ".join(sorted(region_data["neighbors"], key=natural_sort_key))
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
    .toolbar {{
      display: flex;
      gap: 10px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .toggle {{
      border: 1px solid #c9c1b2;
      background: #f4efe4;
      color: #1f2933;
      border-radius: 999px;
      padding: 8px 14px;
      font: inherit;
      font-size: 14px;
      cursor: pointer;
    }}
    .toggle.active {{
      background: #30638e;
      color: white;
      border-color: #30638e;
    }}
    .map-view {{
      display: none;
    }}
    .map-view.active {{
      display: block;
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
    .edge {{
      stroke: var(--line);
      stroke-width: 2;
      opacity: 0.85;
    }}
    .node {{
      stroke: #51463b;
      stroke-width: 1.5;
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
        {"".join([
          "<div class='toolbar'>"
          "<button class='toggle active' type='button' data-view-target='borders'>Shared Borders</button>"
          "<button class='toggle' type='button' data-view-target='graph'>Connection Lines</button>"
          "</div>"
          f"<div class='map-view active' data-view='borders'>{border_svg}</div>"
          f"<div class='map-view' data-view='graph'>{graph_svg}</div>"
          if has_exact_border_view
          else
          "<div class='toolbar'>"
          "<button class='toggle active' type='button' data-view-target='graph'>Connection Lines</button>"
          "</div>"
          f"<div class='map-view active' data-view='graph'>{graph_svg}</div>"
        ])}
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
          {
            "Use Shared Borders for the map-style view and Connection Lines for the explicit adjacency "
            "graph. The graph view is the ground-truth fallback whenever you want to inspect links directly."
            if has_exact_border_view
            else
            "This map currently uses only the explicit Connection Lines view because the temporary "
            "shared-borders renderer cannot represent this topology without implying false adjacency."
          }
        </p>
      </aside>
    </div>
  </div>
  <script>
    const buttons = document.querySelectorAll('[data-view-target]');
    const views = document.querySelectorAll('[data-view]');

    for (const button of buttons) {{
      button.addEventListener('click', () => {{
        const target = button.getAttribute('data-view-target');

        for (const otherButton of buttons) {{
          otherButton.classList.toggle('active', otherButton === button);
        }}

        for (const view of views) {{
          view.classList.toggle('active', view.getAttribute('data-view') === target);
        }}
      }});
    }}
  </script>
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
