"""
Read OG_WELL_COMPLETION_DATA_TABLE.dsv and produce a well-count-per-lease table.

Output schema: lease_key (str), wells (int)
  - lease_key matches the production and leases tables: "08-12345-O"
  - wells = count of distinct WELL_NO values on the lease (a recompleted well
    keeps its WELL_NO so it is counted once)

district_no is the DISTRICT_NO code in the dump, not the district name.
District 08 (Midland / Permian Basin) is code '10', not '08'.
"""
from pathlib import Path

import duckdb
import pandas as pd


def _dsv(path: str | Path) -> str:
    safe = str(path).replace("\\", "/")
    return f"read_csv('{safe}', delim='}}', header=true, all_varchar=true, quote='')"


def load_well_counts(dsv_path: str | Path, district_no: str = "10") -> pd.DataFrame:
    """Return a DataFrame with columns lease_key (str) and wells (int).

    Reads from OG_WELL_COMPLETION_DATA_TABLE.dsv (or the sample equivalent).
    """
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            DISTRICT_NAME || '-' || LEASE_NO || '-' || OIL_GAS_CODE AS lease_key,
            COUNT(DISTINCT WELL_NO)::INTEGER AS wells
        FROM {_dsv(dsv_path)}
        WHERE DISTRICT_NO = '{district_no}'
        GROUP BY DISTRICT_NAME, LEASE_NO, OIL_GAS_CODE
        ORDER BY lease_key
    """).df()
    con.close()
    return df


def save_well_counts(
    dsv_path: str | Path,
    out_path: str | Path = "data/processed/well_counts.parquet",
    district_no: str = "10",
) -> pd.DataFrame:
    """Load well counts and write to Parquet. Returns the DataFrame."""
    df = load_well_counts(dsv_path, district_no)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df
