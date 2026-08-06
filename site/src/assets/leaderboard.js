/* Raincloud-row leaderboard. Each entry is a compact row (dots + distribution
   profile + median tick) that expands on click/tap to a full plot with hover
   tooltips and the entry's statistics. Colors come from CSS theme tokens so
   rows re-render on color-scheme change.

   The distribution curve is NOT a KDE: depth is discrete (0..20) and ceiling-
   bounded, so the curve is a smoothed profile of per-depth counts, clamped to
   the support — a ceiling-hugger's curve piles against the right wall instead
   of bleeding past it. It renders only at n >= CURVE_MIN_N and nonzero
   variance (?curves=N overrides the gate for design preview). */
(function () {
  const data = JSON.parse(document.getElementById("lb-data").textContent);
  const curvesParam = new URLSearchParams(location.search).get("curves");
  const curvesOverride = curvesParam === null ? NaN : Number(curvesParam);
  const CURVE_MIN_N =
    Number.isFinite(curvesOverride) && curvesOverride >= 0 ? curvesOverride : 15;
  const X_MAX = 20;

  const cssVar = (n) =>
    getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  // Control rows (null baselines) always sort last and never take a rank number —
  // they calibrate the board's floor, they don't compete on it.
  const rankSort = (a, b) =>
    (a.control_row === true) - (b.control_row === true) ||
    b.score.ci_lower_median - a.score.ci_lower_median ||
    b.runs.n - a.runs.n ||
    b.score.depth_median - a.score.depth_median;

  function curveProfile(depths) {
    if (depths.length < CURVE_MIN_N || new Set(depths).size < 2) return null;
    let c = Array(X_MAX + 1).fill(0);
    for (const d of depths) c[Math.max(0, Math.min(X_MAX, Math.round(d)))]++;
    for (let pass = 0; pass < 2; pass++) {
      c = c.map(
        (v, i) =>
          ((c[i - 1] ?? 0) + 2 * v + (c[i + 1] ?? 0)) / 4 // bounded: no mass past the walls
      );
    }
    const m = Math.max(...c);
    return c.map((v) => v / m);
  }

  const fmtPct = (v) => Math.round(v * 100) + "%";
  const fmt = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));

  /* ---- collapsed sparkline (static SVG) ---- */
  function sparkline(entry, color, width, height) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.classList.add("spark");
    const x = (d) => 4 + (d / (X_MAX + 0.5)) * (width - 8);
    const prof = curveProfile(entry.runs.depths);
    if (prof) {
      const base = height - 4;
      const pts = prof
        .map((v, i) => `${x(i).toFixed(1)},${(base - v * (height - 10)).toFixed(1)}`)
        .join(" ");
      const path = document.createElementNS(svg.namespaceURI, "polyline");
      path.setAttribute("points", `${x(0)},${base} ${pts} ${x(X_MAX)},${base}`);
      path.setAttribute("fill", color);
      path.setAttribute("fill-opacity", "0.14");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-opacity", "0.5");
      path.setAttribute("stroke-width", "1");
      svg.appendChild(path);
    }
    // dot stack: identical depths pile upward so ties stay visible
    const seen = {};
    for (const d of entry.runs.depths) {
      const k = Math.round(d * 2);
      seen[k] = (seen[k] || 0) + 1;
      const c = document.createElementNS(svg.namespaceURI, "circle");
      c.setAttribute("cx", x(d).toFixed(1));
      c.setAttribute("cy", (height - 7 - (seen[k] - 1) * 5).toFixed(1));
      c.setAttribute("r", 2.8);
      c.setAttribute("fill", color);
      c.setAttribute("fill-opacity", "0.8");
      svg.appendChild(c);
    }
    const med = document.createElementNS(svg.namespaceURI, "rect");
    med.setAttribute("x", (x(entry.score.depth_median) - 1).toFixed(1));
    med.setAttribute("y", 2);
    med.setAttribute("width", 2);
    med.setAttribute("height", height - 6);
    med.setAttribute("fill", cssVar("--ink"));
    svg.appendChild(med);
    return svg;
  }

  /* ---- expanded plot (Observable Plot, hover tooltips) ---- */
  function bigPlot(entry, color, width) {
    const runs = entry.runs.depths.map((depth, i) => ({
      depth,
      run: i + 1,
      exit_rate: entry.runs.exit_rate,
    }));
    const prof = curveProfile(entry.runs.depths);
    const profPts = prof ? prof.map((v, i) => ({ depth: i, v })) : [];
    return Plot.plot({
      width,
      height: 150,
      marginLeft: 10,
      marginRight: 10,
      style: { background: "transparent", color: cssVar("--ink-2"), fontSize: "12px" },
      x: { label: "depth (gates cleared)", domain: [0, X_MAX + 1], grid: true },
      y: { axis: null },
      marks: [
        prof &&
          Plot.areaY(profPts, {
            x: "depth",
            y: (d) => d.v,
            fill: color,
            fillOpacity: 0.12,
            curve: "natural",
          }),
        prof &&
          Plot.lineY(profPts, {
            x: "depth",
            y: (d) => d.v,
            stroke: color,
            strokeOpacity: 0.5,
            curve: "natural",
          }),
        Plot.dot(
          runs,
          Plot.dodgeY({
            x: "depth",
            r: 5,
            fill: color,
            fillOpacity: 0.8,
            anchor: "bottom",
            tip: true,
          })
        ),
        Plot.ruleX([entry.score.depth_median], {
          stroke: cssVar("--ink"),
          strokeWidth: 2.5,
        }),
        Plot.text([entry.score.ci_lower_median], {
          x: (d) => d,
          text: () => "▲",
          frameAnchor: "bottom",
          dy: 6,
          fill: cssVar("--muted"),
        }),
      ].filter(Boolean),
    });
  }

  function statsGrid(entry) {
    const s = [
      ["rank bound", entry.score.ci_lower_median],
      ["median depth", entry.score.depth_median],
      [
        "runs (n)",
        entry.declared
          ? `${entry.runs.n} of ${entry.declared.planned_n} declared`
          : entry.runs.n,
      ],
      ["exit rate", fmtPct(entry.runs.exit_rate)],
      ["turns/gate", fmt(entry.runs.turns_per_gate_mean)],
      ["turns (mean)", fmt(entry.runs.turns_mean, 1)],
      ["consistency", fmt(entry.runs.consistency_mean)],
      ["wall time (mean)", entry.runs.elapsed_mean_s ? Math.round(entry.runs.elapsed_mean_s) + "s" : "—"],
      ["arm / source", entry.source.arm + " · " + entry.source.dataset.split("/").pop()],
      [
        "CI",
        `one-sided ${Math.round(entry.score.bootstrap.level * 100)}% bootstrap lower bound on median (B=${entry.score.bootstrap.B.toLocaleString()})`,
      ],
    ];
    const div = document.createElement("dl");
    div.className = "stats-grid";
    for (const [k, v] of s) {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      div.append(dt, dd);
    }
    return div;
  }

  /* ---- axis header shared by a board ---- */
  function axisHeader(width) {
    const h = 22;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", width);
    svg.setAttribute("height", h);
    const x = (d) => 4 + (d / (X_MAX + 0.5)) * (width - 8);
    for (let d = 0; d <= X_MAX; d += 5) {
      const t = document.createElementNS(svg.namespaceURI, "text");
      t.setAttribute("x", x(d));
      t.setAttribute("y", 12);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("fill", cssVar("--muted"));
      t.setAttribute("font-size", "11");
      t.textContent = d;
      svg.appendChild(t);
      const tick = document.createElementNS(svg.namespaceURI, "rect");
      tick.setAttribute("x", x(d) - 0.5);
      tick.setAttribute("y", 15);
      tick.setAttribute("width", 1);
      tick.setAttribute("height", 5);
      tick.setAttribute("fill", cssVar("--baseline"));
      svg.appendChild(tick);
    }
    return svg;
  }

  /* ---- a board (one lane/division) ---- */
  function board(container) {
    const lane = container.dataset.lane;
    const division = container.dataset.division || null;
    let entries = data.filter((e) => e.lane === lane);
    if (division) entries = entries.filter((e) => e.pinned_model.id === division);
    entries.sort(rankSort);

    const colorOf = (e) =>
      e.control_row
        ? cssVar("--muted")
        : lane === "harness" && e.harness.name.startsWith("wiped")
          ? cssVar("--series-2")
          : cssVar("--series-1");
    const nameOf = (e) => (lane === "model" ? e.model.display : e.harness.name);

    container.replaceChildren();

    const head = document.createElement("div");
    head.className = "board-row board-head";
    head.innerHTML =
      '<span class="rk"></span><span class="nm"></span><span class="strip-slot"></span>' +
      '<span class="num bound">bound</span><span class="num med">med</span><span class="num exit">exit</span><span class="caret"></span>';
    container.appendChild(head);
    const stripW = head.querySelector(".strip-slot").clientWidth || 320;
    const axisSlot = head.querySelector(".strip-slot");
    const axisLabel = document.createElement("span");
    axisLabel.className = "axis-label";
    axisLabel.textContent = "depth (gates cleared) →";
    axisSlot.append(axisLabel, axisHeader(stripW));

    let rankNo = 0;
    for (const e of entries) {
      const row = document.createElement("div");
      row.className = "board-row entry";
      row.setAttribute("role", "button");
      row.setAttribute("tabindex", "0");
      row.setAttribute("aria-expanded", "false");

      const rk = document.createElement("span");
      rk.className = "rk";
      rk.textContent = e.control_row ? "—" : ++rankNo;
      const nm = document.createElement("span");
      nm.className = "nm";
      nm.textContent = nameOf(e);
      if (e.ceiling_row) {
        const b = document.createElement("span");
        b.className = "badge ceiling";
        b.textContent = "at map ceiling";
        nm.appendChild(b);
      }
      if (e.control_row) {
        const b = document.createElement("span");
        b.className = "badge control";
        b.textContent = "null control";
        nm.appendChild(b);
      }
      if (e.declared && e.runs.n < e.declared.planned_n) {
        const b = document.createElement("span");
        b.className = "badge partial";
        b.textContent = `partial cohort ${e.runs.n}/${e.declared.planned_n}`;
        nm.appendChild(b);
      }
      const strip = document.createElement("span");
      strip.className = "strip-slot";
      strip.appendChild(sparkline(e, colorOf(e), stripW, 30));
      const bound = document.createElement("span");
      bound.className = "num bound";
      bound.textContent = e.score.ci_lower_median;
      const med = document.createElement("span");
      med.className = "num med";
      med.textContent = e.score.depth_median;
      const exit = document.createElement("span");
      exit.className = "num exit";
      exit.textContent = fmtPct(e.runs.exit_rate);
      const caret = document.createElement("span");
      caret.className = "caret";
      caret.textContent = "▸";
      row.append(rk, nm, strip, bound, med, exit, caret);

      const detail = document.createElement("div");
      detail.className = "board-detail";
      detail.hidden = true;

      const toggle = () => {
        const open = detail.hidden;
        detail.hidden = !open;
        row.setAttribute("aria-expanded", String(open));
        caret.textContent = open ? "▾" : "▸";
        if (open && !detail.dataset.rendered) {
          detail.appendChild(bigPlot(e, colorOf(e), Math.min(container.clientWidth - 24, 860)));
          detail.appendChild(statsGrid(e));
          if (e.harness?.summary) {
            const p = document.createElement("p");
            p.className = "harness-note";
            p.textContent = e.harness.summary;
            detail.appendChild(p);
          }
          detail.dataset.rendered = "1";
        }
      };
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggle();
        }
      });

      container.append(row, detail);
    }
  }

  function drawAll() {
    document.querySelectorAll(".board").forEach(board);
  }
  drawAll();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    document
      .querySelectorAll(".board-detail")
      .forEach((d) => ((d.dataset.rendered = ""), d.replaceChildren(), (d.hidden = true)));
    drawAll();
  });
})();
