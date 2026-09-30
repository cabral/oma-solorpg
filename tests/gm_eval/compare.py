"""Did a change to the GM's instructions help? python3 tests/gm_eval/compare.py <commit A> <commit B> [options]

Reads results.tsv (every run adds a line) and, for each score and each cost, sets the runs of one commit
beside the runs of another. A difference only counts when it is larger than the runs of either commit
differ among themselves: one run of each says nothing, since the judge and the GM both vary. Play each
commit with --repeat 3 (and a fixed --seed) before comparing, and commit before you measure: a "-dirty"
commit is whatever the tree was that day.
"""

import argparse
import csv
import statistics
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results.tsv"
# (column, higher is better)
METRICS = [("rules", True), ("adventure", True), ("state", True), ("secrecy", True), ("narration", True), ("agency", True), ("table", True),
           ("expectations", True), ("refused", False), ("median_s", False), ("commands_per_turn", False), ("model_calls_per_turn", False), ("cost_usd", False)]


def load(path=RESULTS):
    with open(path, encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def number(row, column):
    """A cell as a number: "3/4" expectations are 0.75, a blank is missing."""
    text = (row.get(column) or "").strip()
    if not text:
        return None
    try:
        if "/" in text:
            met, total = text.split("/")
            return int(met) / int(total) if int(total) else None
        return float(text)
    except ValueError:
        return None


def runs(rows, commit, scenario=None, model=None, effort=None):
    """The rows of one commit (a prefix of it is enough), optionally of one scenario, model and effort."""
    return [r for r in rows if r["commit"].startswith(commit) and (not scenario or r["scenario"] == scenario)
            and (not model or r["model"] == model) and (not effort or r["effort"] == effort)]


def compare(a, b):
    """{metric: verdict} for two lists of runs. `worse`, `better`, `same` (within the runs' own spread),
    or `too few runs` (fewer than two of either)."""
    result = {}
    for column, higher in METRICS:
        xs = [v for v in (number(r, column) for r in a) if v is not None]
        ys = [v for v in (number(r, column) for r in b) if v is not None]
        if not xs or not ys:
            continue
        line = {"a": xs, "b": ys, "mean_a": statistics.mean(xs), "mean_b": statistics.mean(ys)}
        if len(xs) < 2 or len(ys) < 2:
            line["verdict"] = "too few runs"
        else:
            spread = max(statistics.stdev(xs), statistics.stdev(ys))
            gap = line["mean_b"] - line["mean_a"]
            line["spread"] = spread
            if abs(gap) <= spread:
                line["verdict"] = "same"
            else:
                line["verdict"] = "better" if (gap > 0) == higher else "worse"
        result[column] = line
    return result


def render(a_name, b_name, a, b, result):
    lines = [f"{a_name}: {len(a)} runs. {b_name}: {len(b)} runs.", ""]
    if not result:
        return "\n".join(lines + ["Nothing to compare: no run of either has these columns filled."])
    width = max(len(m) for m in result)
    lines.append(f"{'':{width}}  {a_name:>12}  {b_name:>12}  {'spread':>7}  verdict")
    for column, line in result.items():
        spread = f"{line['spread']:.2f}" if "spread" in line else "-"
        lines.append(f"{column:{width}}  {line['mean_a']:>12.2f}  {line['mean_b']:>12.2f}  {spread:>7}  {line['verdict']}")
    lines += ["", "better and worse are for B against A, and count only past the larger spread of the two commits' own runs."]
    if any(line["verdict"] == "too few runs" for line in result.values()):
        lines.append("Some columns have too few runs to say: play each commit with --repeat 3.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("a", help="the commit to compare from (a prefix is enough)")
    parser.add_argument("b", help="the commit to compare to")
    parser.add_argument("--scenario", help="only this scenario's runs")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--results", default=str(RESULTS))
    args = parser.parse_args(argv)
    rows = load(args.results) if Path(args.results).exists() else []
    a = runs(rows, args.a, args.scenario, args.model, args.effort)
    b = runs(rows, args.b, args.scenario, args.model, args.effort)
    if not a or not b:
        print(f"no runs for {args.a if not a else args.b} in {args.results}: play it first (python3 tests/gm_eval/run.py --repeat 3 --seed 1)", file=sys.stderr)
        return 1
    print(render(args.a, args.b, a, b, compare(a, b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
