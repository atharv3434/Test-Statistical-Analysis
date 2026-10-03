"""
Hypothesis tests, effect sizes, and confidence intervals for comparing
two groups in an A/B test.

Two test types are implemented, matched to the kind of metric:
- **Two-proportion z-test** for binary outcomes (e.g. conversion rate).
- **Welch's t-test** for continuous outcomes (e.g. revenue, load time) —
  Welch's version is used rather than the standard (Student's) t-test
  because it does not assume the two groups have equal variance, which is
  safer by default since A/B test groups often do differ in variance.

Every test returns not just a p-value but an effect size and confidence
interval too — a p-value alone can't tell you whether an effect is large
enough to matter, only whether it's distinguishable from noise.
"""

import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest


def test_proportion(control_values, treatment_values, alpha=0.05):
    """Two-proportion z-test comparing conversion rates (or any 0/1 metric).

    Effect size: Cohen's h, the standard effect size for a difference
    between two proportions (it's on the arcsine-transformed scale, which
    stabilizes variance better than a raw proportion difference,
    especially near 0 or 1).
    """
    n_control, n_treatment = len(control_values), len(treatment_values)
    successes_control = int(np.sum(control_values))
    successes_treatment = int(np.sum(treatment_values))

    p_control = successes_control / n_control
    p_treatment = successes_treatment / n_treatment

    z_stat, p_value = proportions_ztest(
        count=[successes_treatment, successes_control],
        nobs=[n_treatment, n_control],
    )

    diff = p_treatment - p_control
    se_diff = np.sqrt(p_control * (1 - p_control) / n_control + p_treatment * (1 - p_treatment) / n_treatment)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci_low, ci_high = diff - z_crit * se_diff, diff + z_crit * se_diff

    cohens_h = 2 * np.arcsin(np.sqrt(p_treatment)) - 2 * np.arcsin(np.sqrt(p_control))
    relative_lift = (diff / p_control) if p_control > 0 else float("nan")

    return {
        "test": "two-proportion z-test",
        "control_rate": p_control,
        "treatment_rate": p_treatment,
        "absolute_diff": diff,
        "relative_lift": relative_lift,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "statistic": float(z_stat),
        "p_value": float(p_value),
        "effect_size": float(cohens_h),
        "effect_size_name": "Cohen's h",
    }


def test_continuous(control_values, treatment_values, alpha=0.05):
    """Welch's t-test comparing means of a continuous metric.

    Effect size: Cohen's d, using the pooled standard deviation.
    """
    control_values = np.asarray(control_values, dtype=np.float64)
    treatment_values = np.asarray(treatment_values, dtype=np.float64)

    mean_control, mean_treatment = control_values.mean(), treatment_values.mean()
    n_control, n_treatment = len(control_values), len(treatment_values)
    var_control, var_treatment = control_values.var(ddof=1), treatment_values.var(ddof=1)

    t_stat, p_value = stats.ttest_ind(treatment_values, control_values, equal_var=False)

    # Welch-Satterthwaite confidence interval for the difference in means
    se_diff = np.sqrt(var_control / n_control + var_treatment / n_treatment)
    df = (var_control / n_control + var_treatment / n_treatment) ** 2 / (
        (var_control / n_control) ** 2 / (n_control - 1) + (var_treatment / n_treatment) ** 2 / (n_treatment - 1)
    )
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    diff = mean_treatment - mean_control
    ci_low, ci_high = diff - t_crit * se_diff, diff + t_crit * se_diff

    pooled_std = np.sqrt(((n_control - 1) * var_control + (n_treatment - 1) * var_treatment) / (n_control + n_treatment - 2))
    cohens_d = diff / pooled_std if pooled_std > 0 else float("nan")
    relative_lift = (diff / mean_control) if mean_control != 0 else float("nan")

    return {
        "test": "Welch's t-test",
        "control_mean": mean_control,
        "treatment_mean": mean_treatment,
        "absolute_diff": diff,
        "relative_lift": relative_lift,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "statistic": float(t_stat),
        "p_value": float(p_value),
        "effect_size": float(cohens_d),
        "effect_size_name": "Cohen's d",
        "degrees_of_freedom": float(df),
    }


def apply_multiple_testing_correction(p_values, method="benjamini_hochberg", alpha=0.05):
    """Adjust p-values for testing multiple metrics at once.

    Testing several metrics in the same experiment inflates the chance that
    at least one comes back "significant" purely by chance (the multiple
    comparisons problem) — e.g. with 3 independent tests at alpha=0.05, the
    chance of at least one false positive is roughly 1-(0.95)^3 ≈ 14%, not 5%.

    - "bonferroni": simple and conservative — divides alpha by the number
      of tests. Controls the family-wise error rate.
    - "benjamini_hochberg": less conservative, controls the (less strict)
      false discovery rate — usually preferred when testing more than a
      couple of metrics.
    - "none": no correction (not recommended with >1 metric, included only
      for comparison).
    """
    p_values = np.asarray(p_values, dtype=np.float64)
    n = len(p_values)

    if method == "none" or n <= 1:
        return p_values, (p_values < alpha)

    if method == "bonferroni":
        adjusted = np.clip(p_values * n, 0, 1)
        return adjusted, (adjusted < alpha)

    if method == "benjamini_hochberg":
        order = np.argsort(p_values)
        ranked = p_values[order]
        adjusted_sorted = ranked * n / (np.arange(n) + 1)
        # enforce monotonicity (standard BH step-up correction)
        adjusted_sorted = np.minimum.accumulate(adjusted_sorted[::-1])[::-1]
        adjusted_sorted = np.clip(adjusted_sorted, 0, 1)

        adjusted = np.empty(n)
        adjusted[order] = adjusted_sorted
        return adjusted, (adjusted < alpha)

    raise ValueError(f"Unknown correction method: {method}")
