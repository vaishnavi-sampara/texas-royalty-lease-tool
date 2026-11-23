# Contributing

## Workflow
1. Claim a task on the CDF project board.
2. Pull the latest main: `git checkout main` then `git pull`.
3. Create a branch: `git checkout -b feature/<short-task-name>`
   (for example, feature/eia-price-loader)
4. Make small commits with clear messages, for example:
   "Add EIA price loader" or "Fix lease key for gas leases".
5. Push your branch: `git push -u origin feature/<short-task-name>`
6. Open a pull request to main, fill in the template, and request one reviewer.
7. Merge after approval, then mark the task done on the board.

## Code standards
- Python 3.11
- Put code in the right folder: pipeline/, forecasting/, valuation/, app/
- Add a pytest test in tests/ for every new function
- Never commit raw data: data/raw/ is ignored by Git
- Follow the table formats in docs/data_contracts.md

## Reviewing a pull request
- Check that the code does what the task says
- Run the tests locally if you can
- Leave clear, friendly comments; approve when it's ready

## Where code goes
- One module per task, in the folder for that step: pipeline/, forecasting/, valuation/ or app/
- Name the file after your task (e.g. pipeline/load_prices.py)
- One test file per module: tests/test_<module_name>.py
- Outputs go to data/processed/ in the formats in docs/data_contracts.md
- Check the repo first so two people don't create the same file
