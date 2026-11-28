"""Build the District 08 production table from OG_LEASE_CYCLE_DATA_TABLE.dsv.

The raw file is about 13 GB and '}'-delimited, so it is read in chunks.
Output: data/processed/production.parquet, in the format from docs/data_contracts.md.

DISTRICT_NO in the dump is an internal code, not the district. District 08 is
DISTRICT_NAME '08', which is DISTRICT_NO '10' (code '08' is District 7B).
Rows with a blank DISTRICT_NAME are matched on DISTRICT_NO '10' instead.

Usage from the command line:
    python -m pipeline.load_production
"""

import argparse
import csv
from pathlib import Path

import pandas as pd

DISTRICT = "08"
DISTRICT_NO = "10"
START_MONTH = 201501
LATEST_COMPLETE_MONTH = "2026-07"
CHUNK_SIZE = 1_000_000

DATA_CONTRACT_COLUMNS = [
    "lease_key",
    "district",
    "oil_gas_code",
    "year_month",
    "oil_bbl",
    "gas_mcf",
    "is_complete",
]
TEXT_COLUMNS = ["DISTRICT_NO", "DISTRICT_NAME", "LEASE_NO", "OIL_GAS_CODE", "CYCLE_YEAR_MONTH"]
VOLUME_COLUMNS = ["LEASE_OIL_PROD_VOL", "LEASE_COND_PROD_VOL", "LEASE_GAS_PROD_VOL", "LEASE_CSGD_PROD_VOL"]

DEFAULT_INPUT_PATH = Path("data/raw/OG_LEASE_CYCLE_DATA_TABLE.dsv")
DEFAULT_OUTPUT_PATH = Path("data/processed/production.parquet")


def read_chunks(dsv_path: Path, chunk_size: int = CHUNK_SIZE):
    """Read the raw file in chunks, keeping only the columns we need."""
    # IDs are read as text to keep leading zeros.
    # QUOTE_NONE because some lease names contain quotes.
    return pd.read_csv(
        dsv_path,
        sep="}",
        usecols=TEXT_COLUMNS + VOLUME_COLUMNS,
        dtype={col: str for col in TEXT_COLUMNS},
        quoting=csv.QUOTE_NONE,
        chunksize=chunk_size,
    )


def filter_district_08(chunk: pd.DataFrame, start_month: int = START_MONTH) -> pd.DataFrame:
    """Keep District 08 rows from start_month onward."""
    name = chunk["DISTRICT_NAME"].fillna("").str.strip()
    is_08 = (name == DISTRICT) | ((name == "") & (chunk["DISTRICT_NO"] == DISTRICT_NO))
    in_period = chunk["CYCLE_YEAR_MONTH"].astype(int) >= start_month
    return chunk[is_08 & in_period]


def to_contract_format(chunk: pd.DataFrame, latest_complete_month: str = LATEST_COMPLETE_MONTH) -> pd.DataFrame:
    """Turn raw rows into the production table columns."""
    year_month = pd.to_datetime(chunk["CYCLE_YEAR_MONTH"], format="%Y%m").astype("datetime64[us]")
    df = pd.DataFrame({
        "lease_key": DISTRICT + "-" + chunk["LEASE_NO"] + "-" + chunk["OIL_GAS_CODE"],
        "district": DISTRICT,
        "oil_gas_code": chunk["OIL_GAS_CODE"],
        "year_month": year_month,
        "oil_bbl": chunk["LEASE_OIL_PROD_VOL"].astype(float) + chunk["LEASE_COND_PROD_VOL"],
        "gas_mcf": chunk["LEASE_GAS_PROD_VOL"].astype(float) + chunk["LEASE_CSGD_PROD_VOL"],
        "is_complete": year_month <= pd.Timestamp(latest_complete_month),
    })
    return df[DATA_CONTRACT_COLUMNS]


def drop_never_producing(df: pd.DataFrame) -> pd.DataFrame:
    """Drop leases with no oil or gas in any month (rule 3 in the data contract)."""
    produced = (df["oil_bbl"] > 0) | (df["gas_mcf"] > 0)
    producing_leases = df.loc[produced, "lease_key"].unique()
    return df[df["lease_key"].isin(producing_leases)]


def load_production(
    dsv_path: Path,
    chunk_size: int = CHUNK_SIZE,
    start_month: int = START_MONTH,
    latest_complete_month: str = LATEST_COMPLETE_MONTH,
) -> pd.DataFrame:
    """Return the District 08 production table, sorted by lease_key and year_month."""
    parts = []
    for chunk in read_chunks(dsv_path, chunk_size):
        kept = filter_district_08(chunk, start_month)
        if not kept.empty:
            parts.append(to_contract_format(kept, latest_complete_month))

    if not parts:
        raise ValueError(f"No District {DISTRICT} rows from {start_month} found in {dsv_path}")

    # Rule 3 needs each lease's full history, so it runs after all chunks are read
    df = drop_never_producing(pd.concat(parts, ignore_index=True))
    return df.sort_values(["lease_key", "year_month"]).reset_index(drop=True)


def save_production(
    dsv_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    latest_complete_month: str = LATEST_COMPLETE_MONTH,
) -> pd.DataFrame:
    """Build the production table and write it to Parquet. Returns the DataFrame."""
    df = load_production(dsv_path, latest_complete_month=latest_complete_month)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the District 08 production table.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--latest-complete", default=LATEST_COMPLETE_MONTH, help="YYYY-MM")
    args = parser.parse_args()

    df = save_production(args.input, args.output, args.latest_complete)
    print(f"Saved {len(df)} rows for {df['lease_key'].nunique()} leases to {args.output}")


if __name__ == "__main__":
    main()
