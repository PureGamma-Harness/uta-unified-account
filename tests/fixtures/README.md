# Golden risk case

`risk_golden.json` is synthetic and illustrates this project's fixed-rate,
linear-perpetual model. It is not an exchange-provided expected result and does
not validate a real portfolio-margin methodology. Each number is a decimal
string. The account has no unmodelled fees, interest or pending settlements.

Manual calculation in USD:

1. Positive collateral after haircut: `1000 + 0.02 × 50000 × 0.8 = 1800`.
2. Full liabilities: `0.1 × 2000 + 0.005 × 50000 = 450`.
3. Unrealised PnL: `0.1 × (50000 - 48000) + (-1) × (2000 - 2200) = 400`.
4. Risk equity: `1800 - 450 + 400 = 1750`.
5. Initial margin: `0.1 × 50000 × 0.1 + 1 × 2000 × 0.2 = 900`.
6. Maintenance margin: `0.1 × 50000 × 0.05 + 1 × 2000 × 0.1 = 450`.
7. Available margin: `1750 - 900 - 100` existing order reserve `= 750`.

For the immediate sell of `0.15 BTC` at `49900`, the post-fill quantity is
`-0.05 BTC`. The sell fills below the mark, costing `0.15 × 100 = 15`;
the fee is `0.15 × 49900 × 0.001 = 7.485`. Equity is therefore
`1750 - 15 - 7.485 = 1727.515`. New initial margin is
`0.05 × 50000 × 0.1 + 1 × 2000 × 0.2 = 650`; available margin is
`1727.515 - 650 - 100 = 977.515`.

`test_reference_validation.py` checks both this example and 500 deterministic
synthetic cases against `reference_calculator.py`, which rebuilds the portfolio
after each fill using realised PnL and a new entry price, in exact rational
arithmetic. These checks do not establish integration, transactional safety,
correct live pricing, regulatory compliance or exchange parity.
