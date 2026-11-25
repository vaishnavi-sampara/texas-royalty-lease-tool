"""Load and standardize EIA monthly WTI and Henry Hub spot prices."""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

DATA_CONTRACT_COLUMNS = [
    "year_month",
    "wti_usd_bbl",
    "henry_hub_usd_mmbtu",
]

DEFAULT_WTI_PATH = Path("data/raw/Cushing_OK_WTI_Spot_Price_FOB.csv")
DEFAULT_HENRY_HUB_PATH = Path("data/raw/Henry_Hub_Natural_Gas_Spot_Price.csv")
DEFAULT_OUTPUT_PATH = Path("data/processed/prices.csv")


def find_header_row(csv_path: Path) -> int:
    """Return the 0-based line index where the EIA 'Month,...' header begins."""
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f):
            if line.strip().lower().startswith("month,"):
                return idx
    raise ValueError(f"Could not find 'Month,' header row in {csv_path}")


def load_eia_series(csv_path: Path, value_col: str) -> pd.DataFrame:
    """Load one EIA monthly spot-price CSV into (year_month, value_col).

    year_month is formatted as the first day of the month (YYYY-MM-01) per
    docs/data_contracts.md.
    """
    header_row = find_header_row(csv_path)
    df = pd.read_csv(csv_path, skiprows=header_row)

    if df.shape[1] < 2:
        raise ValueError(f"Expected at least 2 columns in {csv_path}, found {df.shape[1]}")

    df = df.iloc[:, :2].copy()
    df.columns = ["month_raw", value_col]

    dates = pd.to_datetime(df["month_raw"].astype(str).str.strip(), format="mixed", errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").astype("float64")
    df["year_month"] = dates.dt.strftime("%Y-%m-01")

    df = (
        df.dropna(subset=["year_month", value_col])
        [["year_month", value_col]]
        .drop_duplicates(subset=["year_month"], keep="last")
        .sort_values("year_month")
        .reset_index(drop=True)
    )
    return df


def build_prices_table(wti_path: Path, henry_hub_path: Path) -> pd.DataFrame:
    """Merge WTI and Henry Hub monthly series into the data-contract schema."""
    wti = load_eia_series(wti_path, "wti_usd_bbl")
    hh = load_eia_series(henry_hub_path, "henry_hub_usd_mmbtu")

    # Outer join preserves months where only one series exists (missing left as NaN)
    merged = (
        pd.merge(wti, hh, on="year_month", how="outer")
        .sort_values("year_month")
        .reset_index(drop=True)
    )
    return merged[DATA_CONTRACT_COLUMNS]


def save_prices(
    wti_path: Path = DEFAULT_WTI_PATH,
    henry_hub_path: Path = DEFAULT_HENRY_HUB_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> pd.DataFrame:
    """Build and write the standardized prices CSV to data/processed/prices.csv."""
    df = build_prices_table(wti_path, henry_hub_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Load EIA WTI and Henry Hub monthly prices.")
    parser.add_argument("--wti", type=Path, default=DEFAULT_WTI_PATH)
    parser.add_argument("--henry-hub", type=Path, default=DEFAULT_HENRY_HUB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    df = save_prices(args.wti, args.henry_hub, args.output)
    print(f"Saved {len(df)} rows to {args.output} ({df['year_month'].min()} to {df['year_month'].max()})")


if __name__ == "__main__":
    main()
