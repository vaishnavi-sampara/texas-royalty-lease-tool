"""Latest-complete-month cut-off.

RRC fills months that operators haven't reported yet with zeros, so the most
recent months of the production table look like every lease stopped producing.
This module uses DuckDB SQL to find the latest month that has at least 95% of
the normal number of producing leases, and flags every later month as
incomplete (is_complete = False), as described in docs/data_contracts.md.

Definitions used here:
- A lease is producing in a month if oil_bbl + gas_mcf > 0 (nulls count as 0).
- The normal number of producing leases is the median monthly count over the
  12 months before the most recent 12 months in the table. This is a choice
  made for this module, not something fixed by the data contract.
- The latest complete month is the latest month whose count is at least
  95% of that normal number.

Usage from the command line (reads and rewrites the production table):
    python -m pipeline.latest_complete_month
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

import duckdb

THRESHOLD = 0.95
BASELINE_MONTHS = 12
DEFAULT_PATH = Path("data/processed/production.parquet")

# Producing leases per month, and how many months back from the newest month.
MONTHLY_PRODUCING_SQL = """
SELECT
    year_month,
    count(DISTINCT lease_key) FILTER (
        WHERE coalesce(oil_bbl, 0) + coalesce(gas_mcf, 0) > 0
    ) AS producing_leases,
    row_number() OVER (ORDER BY year_month DESC) AS months_back
FROM {table}
GROUP BY year_month
"""

# Latest month with at least `threshold` x the normal number of producing leases.
# $1 = threshold, $2 = baseline_months
LATEST_COMPLETE_SQL = """
WITH monthly AS (
""" + MONTHLY_PRODUCING_SQL + """
),
baseline AS (
    SELECT median(producing_leases) AS normal_producing_leases
    FROM monthly
    WHERE months_back > $2 AND months_back <= 2 * $2
)
SELECT
    max(m.year_month) AS latest_complete_month,
    any_value(b.normal_producing_leases) AS normal_producing_leases
FROM monthly AS m, baseline AS b
WHERE m.producing_leases >= $1 * b.normal_producing_leases
"""

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_table_name(table: str) -> str:
    """Table names can't be SQL parameters, so only allow plain identifiers."""
    if not _IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table!r}")
    return table


def latest_complete_month(
    con: duckdb.DuckDBPyConnection,
    table: str = "production",
    threshold: float = THRESHOLD,
    baseline_months: int = BASELINE_MONTHS,
) -> dt.date:
    """Return the latest month with at least `threshold` of the normal number of producing leases.

    Raises ValueError if the table has too few months to measure a baseline,
    or if no month reaches the threshold.
    """
    table = _check_table_name(table)
    n_months = con.execute(f"SELECT count(DISTINCT year_month) FROM {table}").fetchone()[0]
    if n_months <= baseline_months:
        raise ValueError(
            f"Need more than {baseline_months} months of data to measure a baseline; found {n_months}."
        )

    latest, normal = con.execute(
        LATEST_COMPLETE_SQL.format(table=table), [threshold, baseline_months]
    ).fetchone()
    if normal is None or normal == 0:
        raise ValueError("The baseline months have no producing leases.")
    if latest is None:
        raise ValueError(f"No month reaches {threshold:.0%} of the normal number of producing leases.")
    return latest


def flag_incomplete_months(
    con: duckdb.DuckDBPyConnection,
    table: str = "production",
    threshold: float = THRESHOLD,
    baseline_months: int = BASELINE_MONTHS,
) -> duckdb.DuckDBPyRelation:
    """Return the table with is_complete = True up to the latest complete month and False after it.

    If the table already has an is_complete column it is replaced in place;
    otherwise it is added as the last column.
    """
    table = _check_table_name(table)
    latest = latest_complete_month(con, table, threshold, baseline_months)
    return con.sql(_flag_sql(con, table), params=[latest])


def _flag_sql(con: duckdb.DuckDBPyConnection, table: str) -> str:
    """SQL that sets is_complete from the cut-off month passed as $1."""
    columns = [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
    if "is_complete" in columns:
        return f"SELECT * REPLACE (year_month <= $1 AS is_complete) FROM {table}"
    return f"SELECT *, year_month <= $1 AS is_complete FROM {table}"


def _sql_path(path: Path) -> str:
    """A file path as a SQL string literal (file paths can't be SQL parameters here)."""
    return "'" + path.as_posix().replace("'", "''") + "'"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_PATH, help="production table (Parquet)")
    parser.add_argument("--output", type=Path, default=None, help="where to write the flagged table (default: overwrite input)")
    args = parser.parse_args(argv)
    output = args.output or args.input

    con = duckdb.connect()
    con.execute(f"CREATE TABLE production AS SELECT * FROM read_parquet({_sql_path(args.input)})")
    latest = latest_complete_month(con)
    con.execute(f"COPY ({_flag_sql(con, 'production')}) TO {_sql_path(output)} (FORMAT parquet)", [latest])
    print(f"Latest complete month: {latest:%Y-%m}. Wrote {output}.")


if __name__ == "__main__":
    main()
