"""Power analysis: how many users per group would a *future* test need to
reliably detect an effect of a given size?

This answers a different, forward-looking question than the hypothesis
tests in stats_tests.py (which ask "was there a detectable effect in the
data we already have"). Running this before an experiment ("how long do I
need to run this test?") is standard practice — testing too few users risks
missing a real effect (low power); the calculations here use the *current*
data's baseline rate/variance plus a target minimum detectable effect (MDE)
to recommend a sample size.
"""

from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize


def required_sample_size_proportion(baseline_rate, mde_relative, alpha=0.05, power=0.8):
    """Required sample size per group to detect a relative lift of
    `mde_relative` on a baseline conversion rate, via a two-proportion
    z-test.
    """
    target_rate = baseline_rate * (1 + mde_relative)
    effect_size = proportion_effectsize(baseline_rate, target_rate)
    n_per_group = NormalIndPower().solve_power(
        effect_size=effect_size, alpha=alpha, power=power, ratio=1.0, alternative="two-sided",
    )
    return {
        "baseline_rate": baseline_rate,
        "target_rate": target_rate,
        "mde_relative": mde_relative,
        "effect_size": effect_size,
        "n_per_group": int(round(n_per_group)),
    }


def required_sample_size_continuous(baseline_mean, baseline_std, mde_relative, alpha=0.05, power=0.8):
    """Required sample size per group to detect a relative lift of
    `mde_relative` on a baseline mean, via a two-sample t-test, given the
    metric's observed standard deviation.
    """
    delta = baseline_mean * mde_relative
    effect_size = delta / baseline_std if baseline_std > 0 else float("nan")
    n_per_group = TTestIndPower().solve_power(
        effect_size=effect_size, alpha=alpha, power=power, ratio=1.0, alternative="two-sided",
    )
    return {
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "mde_relative": mde_relative,
        "effect_size": effect_size,
        "n_per_group": int(round(n_per_group)),
    }
