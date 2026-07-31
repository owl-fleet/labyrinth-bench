# TASK: LabyrinthBench run-trace renderer (render_trace.py)

Write a Python 3 script `render_trace.py` in the current directory (`/work`) that
renders a completed LabyrinthBench maze run as a static SVG image.

## Invocation

    python3 render_trace.py journal.json deg.json out.svg

- Python 3 STANDARD LIBRARY ONLY (no pip; there is no network).
- Exit code 0 on success; write the SVG to the third argument's path.
- Output must be DETERMINISTIC: running the script twice must produce
  byte-identical files. Never iterate over sets or unsorted dicts when order
  affects output; use the input file order or the sort rules given below.
  No timestamps, no randomness.

## Inputs

`deg.json` — the maze, a directed graph:

    {"id": "<deg id>",
     "nodes": [{"id": "<node id>", "terminal": <bool>}, ...],
     "edges": [{"src": "<id>", "dst": "<id>", "gated": <bool>, "wrong": <bool>}, ...]}

`journal.json` — one run through that maze:

    {"deg_id": "...", "model": "<model name>", "found_exit": <bool>,
     "steps_to_exit": <int>, "step_budget": <int>,
     "events": [{"action": "observe"|"inspect"|"commit"|"note"|"pull",
                 "node_id": "<id>", "steps_used": <int>,
                 "outcome": null|"ok"|"back"|"dead_end"|"exit"|..., ...}, ...]}

Only `commit` events are movement; every other action is ignored by the
renderer. The journey starts at node `start`. The sequence of commit events'
`node_id`s (in order, INCLUDING backtracks) is the route taken.

## Layout (follow exactly — the checker recomputes these formulas)

1. **Depth**: for every node, depth = length of the shortest directed path
   from node `start` to it, using ALL edges (including `wrong` ones).
   If any node is unreachable from `start`, its depth = (max reachable depth) + 1.
2. **Columns**: nodes with the same depth form a column. Within a column,
   sort node ids lexicographically (plain string sort); the position in that
   sorted list is the node's row (0-based).
3. **Coordinates** (all integers; emit them without decimal points):

       x = 80 + depth * 170
       y = 70 + row * 90

4. **Canvas**: W = 160 + max_depth * 170, H = 140 + (max_column_size - 1) * 90,
   where max_depth is the largest depth used and max_column_size is the size of
   the largest column. Root element:

       <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 W H">

## Required SVG content (the checker verifies each item)

- A `<title>` element whose text contains the deg id and the model name.
- A `<style>` element (non-empty) defining the visual appearance of the
  classes below. Colors and styling are yours to choose; a palette that fits
  the site: route/accent `#2a78d6`, success `#008300`, danger `#c0392b`,
  neutral gray `#888`. Dead ends and gated edges should be visually distinct.
- **Edges** — for EVERY edge in `deg.json`, one
  `<line x1="<src.x>" y1="<src.y>" x2="<dst.x>" y2="<dst.y>">` between the two
  node centers, with class `edge`, plus class token `gated` if gated is true,
  plus class token `wrong` if wrong is true (e.g. class="edge gated wrong").
- **Route** — ONE `<polyline>` with class `route` and
  `points="x1,y1 x2,y2 ..."`: the center of `start`, then the center of every
  commit event's `node_id` in event order (backtracks included).
- **Nodes** — for EVERY node, one `<circle cx="<x>" cy="<y>" r="18">` with a
  `data-id="<node id>"` attribute and class `node`, plus class token:
    - `start` if the node id is `start`;
    - `exit`  if the node's `terminal` is true;
    - `deadend` if the node has NO outgoing edges and is not terminal.
  Other nodes get class `node` alone.
- **Step labels** — for EVERY commit event, one `<text>` element with class
  `step`, attribute `data-step="<steps_used>"`, the step number as its text
  content, positioned at

       x = node.x,   y = node.y - 26 - 14 * k

  where k = how many earlier commit events already targeted this same node
  (so repeated visits stack their labels upward instead of overlapping).

Draw order suggestion (not checked): edges first, then the route, then
circles, then text — so nodes sit on top of lines.

## Working method

- The checker is available in this directory: run `python3 renderer_check.py`
  any time to see exactly which requirements pass and fail. The harness runs
  the same checker (a pristine copy) for the final verdict, plus a
  determinism check (two runs must be byte-identical).
- Write the file with a heredoc, e.g.:
  `cat > render_trace.py <<'EOF'` ... `EOF` (one command), then test it.
