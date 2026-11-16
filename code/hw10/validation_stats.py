"""Statistics for Part 3: judge-versus-human agreement and run-to-run repeatability."""

from __future__ import annotations

import math
from itertools import combinations

from scipy.stats import spearmanr


def spearman(human: list[float], judge: list[float]) -> dict[str, float]:
    """Spearman rank correlation (ties get average ranks). NaN when either side is constant."""
    if len(set(human)) < 2 or len(set(judge)) < 2:
        return {"rho": math.nan, "p_value": math.nan, "n": len(human)}
    result = spearmanr(human, judge)
    return {"rho": float(result.statistic), "p_value": float(result.pvalue), "n": len(human)}


def mean_absolute_difference(human: list[float], judge: list[float]) -> float:
    return sum(abs(h - j) for h, j in zip(human, judge, strict=True)) / len(human)


def repeatability(runs: list[list[float]]) -> dict[str, float]:
    """How much the scores move when the same judge is run again on the same inputs.

    `runs` is a list of runs, each a list of per-case scores in the same case order.
    * cases_changed - share of cases whose score is not identical in every run
    * pairs_changed - share of (case, run-pair) comparisons that differ
    * mean_abs_change / max_abs_change - size of the differences over all (case, run-pair) pairs
    * mean_range / max_range - per-case spread (max score - min score across the runs)
    """
    per_case = list(zip(*runs, strict=True))
    pair_diffs = [
        abs(case[a] - case[b]) for case in per_case for a, b in combinations(range(len(runs)), 2)
    ]
    ranges = [max(case) - min(case) for case in per_case]
    return {
        "runs": len(runs),
        "cases": len(per_case),
        "cases_changed": sum(1 for r in ranges if r > 0) / len(per_case),
        "pairs_changed": sum(1 for d in pair_diffs if d > 0) / len(pair_diffs),
        "mean_abs_change": sum(pair_diffs) / len(pair_diffs),
        "max_abs_change": max(pair_diffs),
        "mean_range": sum(ranges) / len(ranges),
        "max_range": max(ranges),
    }
