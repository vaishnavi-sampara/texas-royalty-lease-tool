import datetime as dt

import duckdb
import pandas as pd
import pytest

from pipeline.latest_complete_month import (
    flag_incomplete_months,
    latest_complete_month,
    main,
)


def month(i: int) -> dt.date:
    """Month number i counted from Jan 2024 (0 = 2024-01-01)."""
    return dt.date(2024 + i // 12, i % 12 + 1, 1)


def ts(i: int) -> pd.Timestamp:
    """month(i) as a pandas Timestamp, for comparing with DataFrames that DuckDB returns."""
    return pd.Timestamp(month(i))


def make_production(producing_per_month: list[int], total_leases: int = 100) -> pd.DataFrame:
    """Production table in the data-contract format.

    Every lease has a row every month (like the RRC table). In month i, the first
    producing_per_month[i] leases produce oil; the rest are zero-filled.
    """
    rows = []
    for i, n_producing in enumerate(producing_per_month):
        for lease in range(total_leases):
            rows.append({
                "lease_key": f"08-{lease:05d}-O",
                "district": "08",
                "oil_gas_code": "O",
                "year_month": month(i),
                "oil_bbl": 100.0 if lease < n_producing else 0.0,
                "gas_mcf": 0.0,
            })
    return pd.DataFrame(rows)


def connect(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.register("production_df", df)
    con.execute("CREATE TABLE production AS SELECT * FROM production_df")
    return con


def test_finds_latest_month_before_the_drop_off():
    # 24 months at 100 producing leases, then 98, 80, 0: the last complete month is month 24 (98 >= 95).
    con = connect(make_production([100] * 24 + [98, 80, 0]))
    assert latest_complete_month(con) == month(24)


def test_threshold_is_inclusive_at_95_percent():
    con = connect(make_production([100] * 24 + [95, 94]))
    assert latest_complete_month(con) == month(24)


def test_month_just_below_threshold_is_not_complete():
    con = connect(make_production([100] * 24 + [94]))
    assert latest_complete_month(con) == month(23)


def test_zero_filled_rows_do_not_count_as_producing():
    # Every month has 100 rows, but the last month only has 10 leases with production.
    con = connect(make_production([100] * 24 + [10]))
    assert latest_complete_month(con) == month(23)


def test_gas_only_leases_count_as_producing():
    df = make_production([100] * 25)
    last = df.year_month == month(24)
    df.loc[last, "oil_bbl"] = 0.0
    df.loc[last, "gas_mcf"] = 50.0
    con = connect(df)
    assert latest_complete_month(con) == month(24)


def test_normal_comes_from_the_12_months_before_the_last_12():
    # Months 0-13 have 100 producing leases, months 14-25 have 60. The baseline is
    # months 2-13 (12 to 24 months back), so normal = 100 and the recent months at 60
    # are all below 95%. If all months were used instead, the result would differ.
    con = connect(make_production([100] * 14 + [60] * 12))
    assert latest_complete_month(con) == month(13)


def test_shorter_history_uses_the_months_available_for_the_baseline():
    # 14 months: the baseline is just months 0-1, which still gives a sensible answer.
    con = connect(make_production([100] * 13 + [50]))
    assert latest_complete_month(con) == month(12)


def test_missing_volumes_count_as_zero():
    df = make_production([100] * 25)
    last = df.year_month == month(24)
    df.loc[last, ["oil_bbl", "gas_mcf"]] = None
    con = connect(df)
    assert latest_complete_month(con) == month(23)


def test_negative_volume_does_not_hide_other_production():
    # Each volume is checked on its own: oil 5 with gas -10 is still a producing lease
    # (adding them up would give -5 and wrongly count it as not producing).
    df = make_production([100] * 25)
    last = df.year_month == month(24)
    df.loc[last, "oil_bbl"] = 5.0
    df.loc[last, "gas_mcf"] = -10.0
    con = connect(df)
    assert latest_complete_month(con) == month(24)


def test_rows_without_a_month_are_flagged_incomplete():
    df = make_production([100] * 24 + [98, 0])
    df = pd.concat([df, df.iloc[[0]].assign(year_month=None)], ignore_index=True)
    con = connect(df)
    assert latest_complete_month(con) == month(24)
    flagged = flag_incomplete_months(con).df()
    assert flagged.is_complete.notna().all()
    assert not flagged.loc[flagged.year_month.isna(), "is_complete"].any()


def test_uses_the_latest_month_meeting_the_threshold():
    # The task asks for the latest month with at least 95%, so a later month that
    # recovers to 100 counts even though the month before it dipped.
    con = connect(make_production([100] * 24 + [80, 100, 0]))
    assert latest_complete_month(con) == month(25)


def test_flags_later_months_as_incomplete():
    df = make_production([100] * 24 + [98, 80, 0])
    con = connect(df)
    flagged = flag_incomplete_months(con).df()

    complete = flagged[flagged.year_month <= ts(24)]
    incomplete = flagged[flagged.year_month > ts(24)]
    assert len(flagged) == len(df)
    assert len(complete) == 25 * 100 and complete.is_complete.all()
    assert len(incomplete) == 2 * 100 and not incomplete.is_complete.any()
    assert list(flagged.columns) == list(df.columns) + ["is_complete"]


def test_replaces_an_existing_is_complete_column():
    df = make_production([100] * 24 + [98, 0])
    df["is_complete"] = True
    con = connect(df)
    flagged = flag_incomplete_months(con).df()

    last = flagged[flagged.year_month == ts(25)]
    assert list(flagged.columns) == list(df.columns)
    assert len(last) == 100 and not last.is_complete.any()
    assert flagged[flagged.year_month <= ts(24)].is_complete.all()


def test_needs_more_than_a_baseline_of_months():
    con = connect(make_production([100] * 12))
    with pytest.raises(ValueError, match="more than 12 months"):
        latest_complete_month(con)


def test_rejects_an_unsafe_table_name():
    con = connect(make_production([100] * 25))
    with pytest.raises(ValueError, match="Invalid table name"):
        latest_complete_month(con, table="production; DROP TABLE production")


def test_main_handles_a_path_with_an_apostrophe(tmp_path):
    folder = tmp_path / "ganesh's data"
    folder.mkdir()
    src = folder / "production.parquet"
    make_production([100] * 24 + [98, 0]).to_parquet(src, index=False)

    main(["--input", str(src)])  # default: overwrite the input in place

    flagged = pd.read_parquet(src)
    assert "is_complete" in flagged.columns
    assert not flagged.loc[pd.to_datetime(flagged.year_month) == ts(25), "is_complete"].any()


def test_main_writes_flagged_parquet(tmp_path):
    df = make_production([100] * 24 + [98, 80, 0])
    src = tmp_path / "production.parquet"
    out = tmp_path / "flagged.parquet"
    df.to_parquet(src, index=False)

    main(["--input", str(src), "--output", str(out)])

    flagged = pd.read_parquet(out)
    when = pd.to_datetime(flagged.year_month)
    assert len(flagged) == len(df)
    assert (when > ts(24)).sum() == 200 and not flagged.loc[when > ts(24), "is_complete"].any()
    assert flagged.loc[when <= ts(24), "is_complete"].all()
