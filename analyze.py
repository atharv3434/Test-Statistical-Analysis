"""
Run the full A/B test analysis: hypothesis tests for every configured
metric, multiple-testing correction, effect sizes with confidence
intervals, power analysis, and a full markdown report with plots.

Usage:
    python src/analyze.py [--config config.yaml]
"""

import argparse
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(__file__))
from utils import load_config, load_data
from stats_tests import test_proportion, test_continuous, apply_multiple_testing_correction
from power_analysis import required_sample_size_proportion, required_sample_size_continuous


def plot_proportion(result, label, figures_dir, slug):
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    rates = [result["control_rate"], result["treatment_rate"]]
    ax.bar(["Control", "Treatment"], rates, color=["#3B6E8F", "#C1440E"])
    ax.set_ylabel(label)
    ax.set_title(f"{label}: control vs. treatment")
    for i, r in enumerate(rates):
        ax.text(i, r, f"{r:.1%}", ha="center", va="bottom")
    fig.tight_layout()
    path = os.path.join(figures_dir, f"{slug}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_continuous(control_values, treatment_values, label, figures_dir, slug):
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.boxplot([control_values, treatment_values], tick_labels=["Control", "Treatment"], showmeans=True)
    ax.set_ylabel(label)
    ax.set_title(f"{label}: control vs. treatment")
    fig.tight_layout()
    path = os.path.join(figures_dir, f"{slug}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def interpret_effect_size(name, value):
    value = abs(value)
    if name == "Cohen's d":
        if value < 0.2:
            return "negligible"
        if value < 0.5:
            return "small"
        if value < 0.8:
            return "medium"
        return "large"
    if name == "Cohen's h":
        if value < 0.2:
            return "negligible"
        if value < 0.5:
            return "small"
        if value < 0.8:
            return "medium"
        return "large"
    return "n/a"


def main():
    parser = argparse.ArgumentParser(description="Run the full A/B test analysis.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    os.makedirs(config["figures_dir"], exist_ok=True)

    df = load_data(config["data_path"])
    control = df[df[config["group_col"]] == config["control_label"]]
    treatment = df[df[config["group_col"]] == config["treatment_label"]]
    print(f"Control: {len(control)} users  |  Treatment: {len(treatment)} users\n")

    alpha = config.get("alpha", 0.05)
    results = []
    figure_paths = {}

    for metric in config["metrics"]:
        name, mtype, label = metric["name"], metric["type"], metric["label"]
        c_vals, t_vals = control[name].to_numpy(), treatment[name].to_numpy()

        if mtype == "proportion":
            result = test_proportion(c_vals, t_vals, alpha)
            slug = name
            figure_paths[name] = plot_proportion(result, label, config["figures_dir"], slug)
        elif mtype == "continuous":
            result = test_continuous(c_vals, t_vals, alpha)
            slug = name
            figure_paths[name] = plot_continuous(c_vals, t_vals, label, config["figures_dir"], slug)
        else:
            raise ValueError(f"Unknown metric type: {mtype}")

        result["name"] = name
        result["label"] = label
        results.append(result)

        print(f"--- {label} ({result['test']}) ---")
        print(f"  p-value (raw): {result['p_value']:.4f}")
        print(f"  effect size ({result['effect_size_name']}): {result['effect_size']:.3f}")
        print(f"  95% CI for difference: [{result['ci_low']:.4f}, {result['ci_high']:.4f}]\n")

    # --- Multiple testing correction ---
    method = config.get("multiple_testing_correction", "benjamini_hochberg")
    raw_p = [r["p_value"] for r in results]
    adjusted_p, significant = apply_multiple_testing_correction(raw_p, method, alpha)
    for r, adj_p, sig in zip(results, adjusted_p, significant):
        r["adjusted_p_value"] = float(adj_p)
        r["significant"] = bool(sig)

    print(f"After {method} correction (alpha={alpha}):")
    for r in results:
        verdict = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"  {r['label']:28s} adjusted p={r['adjusted_p_value']:.4f}  -> {verdict}")

    # --- Power analysis (for a future test, given these baselines) ---
    print(f"\nPower analysis (target power={config.get('power_target', 0.8)}, "
          f"MDE={config.get('mde_relative', 0.1)*100:.0f}% relative lift):")
    power_results = {}
    for metric in config["metrics"]:
        name, mtype = metric["name"], metric["type"]
        c_vals = control[name].to_numpy()
        if mtype == "proportion":
            pr = required_sample_size_proportion(
                c_vals.mean(), config.get("mde_relative", 0.1),
                alpha, config.get("power_target", 0.8),
            )
        else:
            pr = required_sample_size_continuous(
                c_vals.mean(), c_vals.std(ddof=1), config.get("mde_relative", 0.1),
                alpha, config.get("power_target", 0.8),
            )
        power_results[name] = pr
        print(f"  {metric['label']:28s} needs ~{pr['n_per_group']} users/group to detect a "
              f"{config.get('mde_relative', 0.1)*100:.0f}% relative lift")

    # --- Report ---
    lines = ["# A/B Test Analysis Report", ""]
    lines.append(f"Control: {len(control)} users  |  Treatment: {len(treatment)} users")
    lines.append("")
    lines.append(f"Multiple-testing correction: **{method}** (alpha = {alpha})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Raw p-value | Adjusted p-value | Significant? | Effect size | Interpretation |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        interp = interpret_effect_size(r["effect_size_name"], r["effect_size"])
        sig_str = "**Yes**" if r["significant"] else "No"
        lines.append(
            f"| {r['label']} | {r['p_value']:.4f} | {r['adjusted_p_value']:.4f} | {sig_str} | "
            f"{r['effect_size_name']}={r['effect_size']:.3f} | {interp} |"
        )
    lines.append("")

    for r in results:
        lines.append(f"## {r['label']}")
        lines.append("")
        lines.append(f"**Test:** {r['test']}")
        lines.append("")
        if "control_rate" in r:
            lines.append(f"- Control rate: {r['control_rate']:.2%}")
            lines.append(f"- Treatment rate: {r['treatment_rate']:.2%}")
        else:
            lines.append(f"- Control mean: {r['control_mean']:.3f}")
            lines.append(f"- Treatment mean: {r['treatment_mean']:.3f}")
        lines.append(f"- Absolute difference: {r['absolute_diff']:.4f}")
        lines.append(f"- Relative lift: {r['relative_lift']:.2%}")
        lines.append(f"- 95% CI for difference: [{r['ci_low']:.4f}, {r['ci_high']:.4f}]")
        lines.append(f"- Raw p-value: {r['p_value']:.4f}  |  Adjusted p-value: {r['adjusted_p_value']:.4f}")
        lines.append(f"- Effect size ({r['effect_size_name']}): {r['effect_size']:.3f} "
                      f"({interpret_effect_size(r['effect_size_name'], r['effect_size'])})")
        lines.append(f"- Verdict: {'**Statistically significant**' if r['significant'] else 'Not statistically significant'} "
                      f"after {method} correction")
        lines.append("")
        lines.append(f"![{r['label']}]({os.path.basename(figure_paths[r['name']])})")
        lines.append("")

    lines.append("## Power analysis: sample size for a future test")
    lines.append("")
    lines.append(f"To reliably (power={config.get('power_target', 0.8)}) detect a "
                  f"{config.get('mde_relative', 0.1)*100:.0f}% relative lift on each metric's "
                  "current baseline:")
    lines.append("")
    lines.append("| Metric | Baseline | Required n per group |")
    lines.append("|---|---|---|")
    for metric in config["metrics"]:
        name = metric["name"]
        pr = power_results[name]
        baseline = pr.get("baseline_rate", pr.get("baseline_mean"))
        lines.append(f"| {metric['label']} | {baseline:.3f} | {pr['n_per_group']:,} |")
    lines.append("")

    with open(config["report_path"], "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nFull report saved to {config['report_path']}")


if __name__ == "__main__":
    main()
