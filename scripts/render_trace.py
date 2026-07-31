import json
import sys
from collections import deque, defaultdict

journal_path, deg_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(journal_path) as f:
    journal = json.load(f)
with open(deg_path) as f:
    deg = json.load(f)

nodes = deg['nodes']
edges = deg['edges']

depths = {}
visited = set()
queue = deque()
start_id = 'start'
queue.append( (start_id, 0) )
visited.add(start_id)

while queue:
    node_id, dist = queue.popleft()
    depths[node_id] = dist
    for edge in edges:
        if edge['src'] == node_id:
            next_node = edge['dst']
            if next_node not in visited:
                visited.add(next_node)
                queue.append( (next_node, dist + 1) )

if depths:
    max_depth = max(depths.values())
else:
    max_depth = 0
for node in nodes:
    node_id = node['id']
    if node_id not in depths:
        depths[node_id] = max_depth + 1

columns = defaultdict(list)
for node in nodes:
    node_id = node['id']
    d = depths[node_id]
    columns[d].append(node_id)
for d in columns:
    columns[d].sort()

node_positions = {}
for node in nodes:
    node_id = node['id']
    d = depths[node_id]
    sorted_nodes = columns[d]
    row = sorted_nodes.index(node_id)
    x = 80 + d * 170
    y = 70 + row * 90
    node_positions[node_id] = (x, y)

max_depth_val = max(depths.values())
max_column_size = max(len(col) for col in columns.values())
W = 160 + max_depth_val * 170
H = 140 + (max_column_size - 1) * 90

commit_events = [event for event in journal['events'] if event['action'] == 'commit']
commit_nodes = [event['node_id'] for event in commit_events]

start_pos = node_positions.get('start', (0, 0))
points = [start_pos]
for node_id in commit_nodes:
    points.append(node_positions.get(node_id, (0, 0)))
points_str = ' '.join(f"{x},{y}" for x, y in points)

style = "<style>\n.edge { stroke: #888; stroke-width: 2; }\n.edge.gated { stroke: #c0392b; }\n.edge.wrong { stroke: #008300; }\n.route { stroke: #2a78d6; stroke-width: 3; fill: none; }\n.node { fill: #888; }\n.node.start { fill: #2a78d6; }\n.node.exit { fill: #008300; }\n.node.deadend { fill: #c0392b; }\n.step { font-family: sans-serif; font-size: 12px; }\n</style>"
title = f"<title>{deg['id']} - {journal['model']}</title>"

edges_xml = []
for edge in edges:
    src_id = edge['src']
    dst_id = edge['dst']
    src_x, src_y = node_positions[src_id]
    dst_x, dst_y = node_positions[dst_id]
    classes = ['edge']
    if edge['gated']:
        classes.append('gated')
    if edge['wrong']:
        classes.append('wrong')
    classes_str = ' '.join(classes)
    edges_xml.append(f"<line x1='{src_x}' y1='{src_y}' x2='{dst_x}' y2='{dst_y}' class='{classes_str}'/>")

nodes_xml = []
for node in nodes:
    node_id = node['id']
    x, y = node_positions[node_id]
    has_outgoing = any(edge['src'] == node_id for edge in edges)
    is_terminal = node['terminal']
    class_name = 'node'
    if node_id == 'start':
        class_name += ' start'
    elif is_terminal:
        class_name += ' exit'
    elif not has_outgoing:
        class_name += ' deadend'
    nodes_xml.append(f"<circle cx='{x}' cy='{y}' r='18' class='{class_name}' data-id='{node_id}'/>")

route_xml = f"<polyline class='route' points='{points_str}'></polyline>"

step_labels_xml = []
visit_counts = defaultdict(int)
for event in commit_events:
    node_id = event['node_id']
    steps_used = event['steps_used']
    count = visit_counts[node_id]
    visit_counts[node_id] += 1
    x, y = node_positions[node_id]
    label_y = y - 26 - 14 * count
    step_labels_xml.append(f"<text x='{x}' y='{label_y}' class='step' data-step='{steps_used}'>{steps_used}</text>")

svg_content = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}'>{title}{style}{''.join(edges_xml)}{route_xml}{''.join(nodes_xml)}{''.join(step_labels_xml)}</svg>"

with open(output_path, 'w') as f:
    f.write(svg_content)
