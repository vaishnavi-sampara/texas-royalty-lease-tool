# Data contracts

Every module reads and writes these tables in exactly these formats.
If a format needs to change, discuss it at stand-up and update this file first.

## 1. production
One row per lease per month. File: data/processed/production.parquet

| Column       | Type   | Description |
|--------------|--------|-------------|
| lease_key    | string | district + lease number + oil/gas code, e.g. "08-12345-O" |
| district     | string | RRC district, e.g. "08" |
| oil_gas_code | string | "O" = oil lease, "G" = gas lease |
| year_month   | date   | First day of the production month |
| oil_bbl      | float  | Oil + condensate (barrels) |
| gas_mcf      | float  | Gas-well gas + casinghead gas (mcf) |
| is_complete  | bool   | True if the month is on or before the latest complete month |

Source columns (RRC lease cycle table):
oil_bbl = LEASE_OIL_PROD_VOL + LEASE_COND_PROD_VOL
gas_mcf = LEASE_GAS_PROD_VOL + LEASE_CSGD_PROD_VOL

## 2. leases
One row per lease. File: data/processed/leases.parquet

| Column        | Type   | Description |
|---------------|--------|-------------|
| lease_key     | string | Same key as production |
| district      | string | RRC district |
| lease_number  | string | RRC lease number |
| oil_gas_code  | string | "O" or "G" |
| lease_name    | string | Lease name |
| operator_name | string | Latest operator |
| field_name    | string | Field name |
| county        | string | County, where available |
| wells         | int    | Number of wells on the lease |

## 3. prices
One row per month. File: data/processed/prices.csv

| Column              | Type  | Description |
|---------------------|-------|-------------|
| year_month          | date  | First day of the month |
| wti_usd_bbl         | float | WTI crude oil spot price (USD per barrel) |
| henry_hub_usd_mmbtu | float | Henry Hub natural gas spot price (USD per MMBtu) |

## Data rules (applied in the pipeline)
1. Lease key = district + lease number + oil/gas code (lease numbers repeat across districts)
2. Months after the latest complete month are flagged is_complete = False
   (RRC fills unreported months with zeros)
3. Leases with no production since 2015 are excluded
4. History is keyed on the lease, not the operator (operators change)

## Sample data
data/sample/ holds the same tables for about 200 District 08 leases, for development and tests.
