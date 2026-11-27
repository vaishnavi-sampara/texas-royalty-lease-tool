from pathlib import Path

import pandas as pd
import pytest

from pipeline.load_well_counts import load_well_counts, save_well_counts

SAMPLE_WELLS = Path("data/sample/raw/well_completion_sample.dsv")
SAMPLE_LEASES = Path("data/sample/leases.parquet")


def test_schema():
    df = load_well_counts(SAMPLE_WELLS)
    assert list(df.columns) == ["lease_key", "wells"]
    assert pd.api.types.is_integer_dtype(df["wells"])


def test_no_duplicate_lease_keys():
    df = load_well_counts(SAMPLE_WELLS)
    assert not df["lease_key"].duplicated().any()


def test_wells_at_least_one():
    df = load_well_counts(SAMPLE_WELLS)
    assert df["wells"].min() >= 1


def test_lease_key_format():
    df = load_well_counts(SAMPLE_WELLS)
    # Format: "08-153631-G"  (two-digit district name, numeric lease number, O or G)
    assert df["lease_key"].str.match(r"^\d{2}-\d+-[OG]$").all(), (
        "Unexpected lease_key values: " + str(df["lease_key"].head())
    )


def test_join_rate_99pct():
    """Well counts must join to at least 99% of the sample leases."""
    well_counts = load_well_counts(SAMPLE_WELLS)
    leases = pd.read_parquet(SAMPLE_LEASES)
    merged = leases.merge(well_counts, on="lease_key", how="left")
    match_rate = merged["wells_y"].notna().mean()
    assert match_rate >= 0.99, f"Join rate {match_rate:.1%} is below 99%"


def test_save_writes_readable_parquet(tmp_path):
    out = tmp_path / "well_counts.parquet"
    df = save_well_counts(SAMPLE_WELLS, out_path=out)
    loaded = pd.read_parquet(out)
    assert list(loaded.columns) == ["lease_key", "wells"]
    assert len(loaded) == len(df)
