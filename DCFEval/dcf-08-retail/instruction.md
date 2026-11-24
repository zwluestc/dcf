# 连锁零售：关店与新店爬坡 | FY2025 valuation

Start from a blank workbook. Read the seven source exhibits in /work/data/. They are original synthetic records, not a public company's filings. Deliver a self-contained /work/output.xlsx. Use the operating memo, budget, two site extracts and treasury/peer and valuation notes to build your own schedules, including peer beta and option dilution. Preserve full precision. Inputs and outputs are in EUR millions and millions of shares unless a source explicitly uses different units. Price per share is in EUR. The required price is DCF intrinsic value, not the market quote.

Reconstruct FY2025 actuals and forecast FY2026–2030 IS, BS and CF. No other balances, tax deferrals, distributions, funding, issuance or transactions. Revenue-equivalent units are net of credits, upfront fees or guarantees as applicable. Forecast revenue = those units times full annual price times the editable multiplier. Budget rate fields suffixed pct are percent, while operations memo ratios are decimal fractions.

Cash COGS is cogs_pct of sales; operating expenses are opex_fixed excluding D&A. Capex equals capex_pct of sales, capitalized in full. D&A uses dep_rate on opening net PP&E plus half current capex. Cap principal repayments at opening debt; interest uses average opening/closing debt at debt_cost. Tax on positive EBT only, no tax benefit or carryforward. Unlevered tax is on positive EBIT. Receivables use sales and dso plus dso_shift; inventory and payables use cash COGS and dio/dpo, on a 365-day basis. NWC = AR + inventory less AP. Equity accumulates net income, and cash accumulates the three cash flows. Operating cash flow is after interest and tax. Show COGS, opex, D&A, tax, interest, capex and principal as positive expenses/outlays; investing/financing cash flows use cash signs. Change in NWC is closing less opening.

CAPM/WACC use the signed treasury policy. Discount each annual FCFF at year-end (1–5) or midyear (0.5–4.5) as signed. Terminal at FY2030 close; perpetuity grows last FCFF by g, exit method uses final EBITDA. Equity value is EV plus FY2025 cash less FY2025 debt. Divide by TSM diluted shares.

## Delivery contract
Inputs!B4:B6 must be editable numeric values, in order: price_multiplier, dso_shift (days), risk_free. Formulas must respond to edits. Other inputs may be laid out freely. Statements!B3:G3 must be the numeric years 2025–2030. Row numbers below denote outputs in that sheet. In B (actuals) only rows 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 22, 23, 24, 25 are required. C:G require every row. Each row name below is also the requested metric definition. Balance-sheet assets are cash + receivables + inventory + net PP&E, liabilities and equity are AP + debt + equity.

- 4: Closing operating units
- 5: Revenue-equivalent billable units
- 6: Revenue
- 7: Cash COGS
- 8: Cash operating expense
- 9: Depreciation
- 10: EBIT
- 11: Interest
- 12: Income tax
- 13: Net income
- 14: Receivables
- 15: Inventory
- 16: Payables
- 17: Net working capital
- 18: Capital expenditure
- 19: Net PP&E
- 20: Term debt
- 21: Principal repaid
- 22: Cash
- 23: Book equity
- 24: Assets
- 25: Liabilities and equity
- 26: Operating cash flow
- 27: Investing cash flow
- 28: Financing cash flow
- 29: Change in cash
- 30: Unlevered cash tax
- 31: Change in NWC
- 32: FCFF
- 33: PV of FCFF

DCF sheet outputs:
- B4: WACC
- B5: Terminal value at FY2030 end
- B6: PV of terminal value
- B7: Enterprise value
- B8: Equity value
- B9: Value per diluted share

Numeric tolerance: greater of EUR million (or native-unit) absolute 0.000001 and 0.0001% relative. Scoring includes base results, cash/equity/FCFF reconciliation and independent recalculation after each of the three editable assumptions changes.

Additional required outputs: DCF!B12 = relevered equity beta; B13 = diluted shares (millions); B14 = median unlevered peer beta; B15 = TSM incremental shares (millions). All four must be formulas referencing upstream cells. Their base values and formulas are graded as part of valuation.
