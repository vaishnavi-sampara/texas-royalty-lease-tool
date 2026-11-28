"""Tests for pipeline/load_production.py, using the sample data in data/sample/."""

import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline.load_production import (
    DATA_CONTRACT_COLUMNS,
    VOLUME_COLUMNS,
    load_production,
    read_chunks,
    save_production,
)

SAMPLE_RAW = Path("data/sample/raw/lease_cycle_sample.dsv")
SAMPLE_PRODUCTION = Path("data/sample/production.parquet")
SAMPLE_INFO = json.loads(Path("data/sample/sample_info.json").read_text())

START_MONTH = SAMPLE_INFO["start_year"] * 100 + 1
LATEST_COMPLETE = pd.Timestamp(SAMPLE_INFO["latest_complete_month"])


def load_sample(chunk_size: int = 1_000_000) -> pd.DataFrame:
    return load_production(SAMPLE_RAW, chunk_size, START_MONTH, SAMPLE_INFO["latest_complete_month"])


@pytest.mark.parametrize("chunk_size", [997, 1_000_000])
def test_matches_sample_production(chunk_size):
    # 997 splits leases across chunks; the result should be the same either way
    expected = pd.read_parquet(SAMPLE_PRODUCTION)
    pd.testing.assert_frame_equal(load_sample(chunk_size), expected)


def test_schema_and_lease_key():
    df = load_sample()
    assert list(df.columns) == DATA_CONTRACT_COLUMNS
    assert (df["district"] == SAMPLE_INFO["district"]).all()
    assert df["lease_key"].str.match(r"^08-\d+-[OG]$").all()
    assert not df.duplicated(["lease_key", "year_month"]).any()


def test_months_and_is_complete():
    df = load_sample()
    assert df["year_month"].min() == pd.Timestamp(f"{SAMPLE_INFO['start_year']}-01")
    assert df.loc[df["is_complete"], "year_month"].max() == LATEST_COMPLETE
    assert df.loc[~df["is_complete"], "year_month"].min() == LATEST_COMPLETE + pd.DateOffset(months=1)


def test_never_producing_leases_dropped():
    raw = pd.concat(read_chunks(SAMPLE_RAW))
    raw_keys = "08-" + raw["LEASE_NO"] + "-" + raw["OIL_GAS_CODE"]
    dropped = set(raw_keys) - set(load_sample()["lease_key"])

    assert raw_keys.nunique() == SAMPLE_INFO["leases_chosen"]
    assert len(dropped) == SAMPLE_INFO["leases_never_producing"]
    assert (raw.loc[raw_keys.isin(dropped), VOLUME_COLUMNS] == 0).all().all()


def test_start_month_filter():
    df = load_production(SAMPLE_RAW, start_month=202001)
    assert df["year_month"].min() == pd.Timestamp("2020-01")


def test_no_rows_raises():
    with pytest.raises(ValueError, match="No District 08 rows"):
        load_production(SAMPLE_RAW, start_month=202701)


def test_save_writes_readable_parquet(tmp_path):
    out = tmp_path / "processed" / "production.parquet"
    df = save_production(SAMPLE_RAW, out, SAMPLE_INFO["latest_complete_month"])
    loaded = pd.read_parquet(out)
    assert len(loaded) == len(df) == SAMPLE_INFO["production_rows"]
