# A/B Test Statistical Analysis

A complete statistical hypothesis testing pipeline for A/B test data:
proper tests matched to each metric type, effect sizes and confidence
intervals (not just p-values), correction for testing multiple metrics at
once, and power analysis for planning a future test.

## Why this is more than "just run a t-test"

A lot of A/B test analysis stops at "is p < 0.05?" This project is built
around a few things real experimentation practice requires beyond that:

1. **The right test for each metric type** — a two-proportion z-test for
   conversion rate, Welch's t-test (not assuming equal variance) for
   continuous metrics like revenue.
2. **Effect sizes, not just p-values** — a p-value tells you whether an
   effect is distinguishable from noise; it says nothing about whether the
   effect is big enough to matter. Every test here also reports Cohen's d
   or Cohen's h, interpreted as negligible/small/medium/large.
3. **Confidence intervals** — the plausible range for the true effect, not
   just a single point estimate.
4. **Multiple testing correction** — testing 3 metrics at alpha=0.05 each
   gives roughly a 14% chance of at least one false positive by chance
   alone, not 5%. This project applies Benjamini-Hochberg (or Bonferroni)
   correction across all tested metrics by default.
5. **Power analysis** — given the data's baseline rate/variance, how many
   users would a *future* test need to reliably detect a given effect size?

## Project structure

```
ab-test-analysis/
├── config.yaml                 # metrics to test, alpha, correction method, power settings
├── requirements.txt
├── data/
│   ├── generate_data.py        # (re)generates the synthetic A/B test data
│   └── ab_test_data.csv        # pre-generated sample data (4000 rows)
├── src/
│   ├── utils.py                # config + data loading
│   ├── stats_tests.py          # the hypothesis tests, effect sizes, CIs, correction
│   ├── power_analysis.py       # required-sample-size calculations
│   └── analyze.py              # CLI: runs everything, writes the report
├── output/
│   ├── figures/                 # per-metric comparison plots
│   └── analysis_report.md       # full report
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Run it

```bash
python src/analyze.py
```

The bundled sample data has a real (deliberately built-in) effect on two
metrics and *no* true effect on a third, so the analysis has to correctly
tell those apart rather than just reporting everything as significant:

```
--- Conversion rate (two-proportion z-test) ---
  p-value (raw): 0.0026
  effect size (Cohen's h): 0.095
  95% CI for difference: [0.0103, 0.0487]

--- Revenue per user (Welch's t-test) ---
  p-value (raw): 0.0022
  effect size (Cohen's d): 0.097
  95% CI for difference: [0.3216, 1.4677]

--- Page load time (ms) (Welch's t-test) ---
  p-value (raw): 0.4011
  effect size (Cohen's d): 0.027
  95% CI for difference: [-4.2542, 10.6297]

After benjamini_hochberg correction (alpha=0.05):
  Conversion rate              adjusted p=0.0039  -> SIGNIFICANT
  Revenue per user             adjusted p=0.0039  -> SIGNIFICANT
  Page load time (ms)          adjusted p=0.4011  -> not significant
```

Exactly matching what was built into the data: conversion rate and revenue
show real, statistically significant lifts; page load time (which was
generated with *identical* distributions in both groups) correctly comes
back as not significant. I verified the two-proportion z-test
independently against a chi-square test on the same 2×2 table — p-values
matched to 4 decimal places (0.0026 = 0.0026).

The power analysis section answers a different question — not "did we find
an effect," but "how big would a future test need to be":

```
Conversion rate              needs ~15984 users/group to detect a 10% relative lift
Revenue per user             needs ~19242 users/group to detect a 10% relative lift
Page load time (ms)          needs ~33 users/group to detect a 10% relative lift
```

Note how different these are: conversion rate and revenue both need tens
of thousands of users per group to detect a *10% relative* lift, because a
10% relative change on a ~10% baseline rate (or a highly variable,
zero-inflated revenue-per-user metric) is a small *absolute* signal to
detect. Page load time needs far fewer, because a 10% relative change on
its mean is large relative to its (comparatively low) variance. This is a
genuinely useful, realistic illustration of why conversion/revenue metrics
often require much longer test durations than operational metrics like
load time.

## Using your own data

1. Replace `data/ab_test_data.csv` with your own data: one row per user,
   a group column, and whatever metric columns you want to test.
2. Update `config.yaml`:
   - `group_col`, `control_label`, `treatment_label` to match your schema
   - `metrics`: list each metric with `type: proportion` (0/1 outcomes) or
     `type: continuous` (numeric outcomes)
3. Re-run `python src/analyze.py`.

## Extending this project

- **Sequential testing**: this project assumes a fixed sample size decided
  in advance — peeking at results repeatedly and stopping early inflates
  the false positive rate. For tests you might want to stop early, look
  into sequential testing methods (e.g. alpha-spending functions).
- **Non-parametric tests**: for heavily skewed metrics (revenue often is),
  consider adding a Mann-Whitney U test as a robustness check alongside
  the t-test.
- **Segment analysis**: extend `analyze.py` to run the same tests within
  subgroups (e.g. new vs. returning users) — just be mindful this adds
  even more multiple-comparisons burden.
- **Bayesian alternative**: for a different philosophy on interpreting
  results, a Bayesian A/B test (e.g. via `pymc` or a Beta-Binomial
  conjugate model for conversion rate) gives a posterior probability that
  treatment beats control, rather than a p-value.
