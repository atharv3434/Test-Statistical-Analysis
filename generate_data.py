"""
Generate synthetic A/B test data with deliberately different outcomes
for three metrics, so the analysis has something genuine to find:

- conversion_rate: a real (moderate) treatment effect built in
- revenue: a real (small) treatment effect built in
- page_load_ms: NO true effect — included on purpose so the analysis has
  to correctly report a null result for at least one metric, rather than
  everything coming back "significant" (which would be a misleadingly
  easy demo).

This project ships with pre-generated data already in place
(data/ab_test_data.csv), so you don't need to run this to try the project
out. Run it again for a different sample size or seed.

Usage:
    python data/generate_data.py [--n-per-group 2000] [--seed 42]
"""

import argparse
import os

import numpy as np
import pandas as pd


def generate_data(rng, n_per_group):
    rows = []

    # True effect sizes (what we're trying to recover with the tests below)
    control_conversion = 0.10
    treatment_conversion = 0.12       # +2pp absolute, +20% relative lift
    control_revenue_mean = 25.0
    treatment_revenue_mean = 26.5     # modest lift, among converters
    page_load_mean = 850.0            # same for both groups — no true effect

    for group, conv_rate, revenue_mean in [
        ("control", control_conversion, control_revenue_mean),
        ("treatment", treatment_conversion, treatment_revenue_mean),
    ]:
        converted = rng.random(n_per_group) < conv_rate
        revenue = np.where(
            converted,
            rng.gamma(shape=4, scale=revenue_mean / 4, size=n_per_group),
            0.0,
        )
        page_load_ms = rng.normal(page_load_mean, 120, size=n_per_group)

        for i in range(n_per_group):
            rows.append({
                "user_id": f"{group[:4]}_{i:05d}",
                "group": group,
                "converted": int(converted[i]),
                "revenue": round(float(revenue[i]), 2),
                "page_load_ms": round(float(page_load_ms[i]), 1),
            })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic A/B test data.")
    parser.add_argument("--n-per-group", type=int, default=2000, help="Users per group")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", default="data/ab_test_data.csv", help="Output CSV path")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    df = generate_data(rng, args.n_per_group)
    df = df.sample(frac=1, random_state=args.seed).reset_index(drop=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows ({args.n_per_group} per group) to {args.out}")
    print(df.groupby("group")[["converted", "revenue", "page_load_ms"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
