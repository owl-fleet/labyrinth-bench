const fs = require("fs");
const path = require("path");

// Rank = the bootstrap lower CI bound on median depth (the conservative bound);
// ties break toward the larger n (more evidence), then the higher median.
function rank(entries) {
  return [...entries].sort(
    (a, b) =>
      b.score.ci_lower_median - a.score.ci_lower_median ||
      b.runs.n - a.runs.n ||
      b.score.depth_median - a.score.depth_median
  );
}

module.exports = () => {
  const dir = path.join(__dirname, "..", "..", "..", "entries");
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort();
  const all = files.map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));

  const model = rank(all.filter((e) => e.lane === "model"));

  const divisions = {};
  for (const e of all.filter((e) => e.lane === "harness")) {
    (divisions[e.pinned_model.id] ??= { pinned: e.pinned_model, entries: [] }).entries.push(e);
  }
  for (const d of Object.values(divisions)) d.entries = rank(d.entries);

  return { all, model, divisions, files };
};
