# Texas Royalty Lease Evaluation Tool

An open-source tool that helps Texas mineral and royalty owners evaluate
offers for their producing oil and gas interests using public data.

## What it does
1. Look up a Texas lease and see its production history
2. Forecast future production (Arps decline-curve analysis)
3. Estimate a value range under different price scenarios
4. Compare a purchase offer against that range

## Data sources
- Texas Railroad Commission, Production Data Query Dump:
  https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/
- EIA WTI crude oil monthly spot price:
  https://www.eia.gov/dnav/pet/hist/rwtcM.htm
- EIA Henry Hub natural gas monthly spot price:
  https://www.eia.gov/dnav/ng/hist/rngwhhdm.htm

## Getting started
1. Clone the repo
2. Install Python 3.11
3. Install libraries: `pip install -r requirements.txt`
4. Use the sample data in data/sample/ for development
5. Read CONTRIBUTING.md before your first pull request

## Project structure
data/        raw (not in Git), processed, sample
pipeline/    data ingestion and data rules
forecasting/ decline-curve forecasting and backtest
valuation/   prices, royalty income, NPV, offer comparison
app/         Streamlit web app
tests/       pytest tests
notebooks/   exploration notebooks
docs/        data contracts, methodology, runbooks

## Disclaimer
Results are informational estimates, not appraisals or financial advice.
