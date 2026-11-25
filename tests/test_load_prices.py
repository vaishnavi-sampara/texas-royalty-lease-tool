"""Unit tests for pipeline/load_prices.py."""

from pathlib import Path
import pandas as pd
import pytest

from pipeline.load_prices import (
    DATA_CONTRACT_COLUMNS,
    build_prices_table,
    find_header_row,
    load_eia_series,
    save_prices,
)

WTI_SAMPLE = """Cushing OK WTI Spot Price FOB
https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=RWTC&f=M
15:55:47 GMT-0600 (Central Standard Time)
Data Source: Thomson Reuters
Month,Cushing OK WTI Spot Price FOB  Dollars per Barrel
Oct 2026,102.07
Sep 2026,97.31
Jan 1996,18.86
"""

HH_SAMPLE = """Henry Hub Natural Gas Spot Price
https://www.eia.gov/dnav/ng/hist/rngwhhdM.htm
15:55:41 GMT-0600 (Central Standard Time)
Data Source: Thomson Reuters
Month,Henry Hub Natural Gas Spot Price Dollars per Million Btu
Oct 2026,2.99
Sep 2026,2.95
"""


def test_find_header_row_locates_month_header(tmp_path: Path) -> None:
    sample = tmp_path / "wti.csv"
    sample.write_text(WTI_SAMPLE, encoding="utf-8")
    assert find_header_row(sample) == 4


def test_find_header_row_raises_when_missing(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("No header here\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header row"):
        find_header_row(bad_file)


def test_load_eia_series_parses_and_sorts(tmp_path: Path) -> None:
    sample = tmp_path / "wti.csv"
    sample.write_text(WTI_SAMPLE, encoding="utf-8")

    df = load_eia_series(sample, "wti_usd_bbl")

    assert list(df.columns) == ["year_month", "wti_usd_bbl"]
    assert list(df["year_month"]) == ["1996-01-01", "2026-09-01", "2026-10-01"]
    assert df["wti_usd_bbl"].dtype == "float64"
    assert df.loc[df["year_month"] == "2026-10-01", "wti_usd_bbl"].iloc[0] == pytest.approx(102.07)


def test_build_prices_table_contract_and_outer_join(tmp_path: Path) -> None:
    wti_file = tmp_path / "wti.csv"
    hh_file = tmp_path / "hh.csv"
    wti_file.write_text(WTI_SAMPLE, encoding="utf-8")
    hh_file.write_text(HH_SAMPLE, encoding="utf-8")

    df = build_prices_table(wti_file, hh_file)

    assert list(df.columns) == DATA_CONTRACT_COLUMNS
    assert list(df["year_month"]) == ["1996-01-01", "2026-09-01", "2026-10-01"]
    assert df["year_month"].is_unique

    oct_row = df.loc[df["year_month"] == "2026-10-01"].iloc[0]
    assert oct_row["wti_usd_bbl"] == pytest.approx(102.07)
    assert oct_row["henry_hub_usd_mmbtu"] == pytest.approx(2.99)

    # Pre-1997 month keeps WTI and leaves Henry Hub missing (NaN, not 0)
    jan96 = df.loc[df["year_month"] == "1996-01-01"].iloc[0]
    assert jan96["wti_usd_bbl"] == pytest.approx(18.86)
    assert pd.isna(jan96["henry_hub_usd_mmbtu"])


def test_save_prices_writes_contract_csv(tmp_path: Path) -> None:
    wti_file = tmp_path / "wti.csv"
    hh_file = tmp_path / "hh.csv"
    out_file = tmp_path / "processed" / "prices.csv"
    wti_file.write_text(WTI_SAMPLE, encoding="utf-8")
    hh_file.write_text(HH_SAMPLE, encoding="utf-8")

    save_prices(wti_file, hh_file, out_file)

    assert out_file.exists()
    reloaded = pd.read_csv(out_file)
    assert list(reloaded.columns) == DATA_CONTRACT_COLUMNS
    assert len(reloaded) == 3
