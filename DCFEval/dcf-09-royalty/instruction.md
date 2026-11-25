# SeaChord Audio (海弦音频) | 特许权：分档计费与最低保底 | FY2025 Valuation from Raw Financial Filings

**MODE: GREENFIELD FROM RAW FILINGS (DATA CLEANING + FULL 3-STATEMENT DCF)**

Start from a blank workbook. Read and clean the three raw unstructured financial filings in `/work/data/` (`annual_report_fy2025.txt`, `management_guidance_fy26_30.md`, and `broker_comps_and_treasury_memo.md` — **no pre-cleaned CSV tables are provided**). They are original synthetic filings, not a public company's filings. You must filter out VOID / FY2024 comparative / superseded Q3 draft / excluded distressed peer entries, normalize mixed reporting units (`EUR`, `EUR thousands`, `EUR millions`, `bp`, `%`), and deliver a self-contained, formula-driven `/work/output.xlsx`.

Preserve full precision. Inputs and outputs are in EUR millions and millions of shares unless a source explicitly uses different units. Price per share is in EUR. The required price is DCF intrinsic value, not the market quote.

Reconstruct FY2025 actuals (income statement and closing balance sheet; FY2025 cash flow statement is NOT required) and forecast FY2026–2030 IS, BS and CF. No other balances, tax deferrals, distributions, funding, issuance or transactions. Revenue-equivalent billable units express full-price equivalent annual volume: deduct expected warranty credits (returns), ADD immediate upfront license fees recognised in full (license), and apply minimum billing guarantees (royalty), strictly following `management_guidance_fy26_30.md`. Forecast revenue = those revenue-equivalent billable units times full annual unit price (converted to EUR millions) times the editable `price_multiplier`.

Cash COGS is cogs_pct of sales; operating expenses are opex_fixed excluding D&A. Capex equals capex_pct of sales, capitalized in full. D&A uses dep_rate on opening net PP&E plus half current capex. Cap principal repayments at opening debt; interest uses average opening/closing debt at debt_cost. Tax on positive EBT only, no tax benefit or carryforward. Unlevered tax is on positive EBIT. Receivables use sales and dso plus dso_shift; inventory and payables use cash COGS and dio/dpo, on a 365-day basis. NWC = AR + inventory less AP. Equity accumulates net income, and cash accumulates the three cash flows. Operating cash flow is after interest and tax. Show COGS, opex, D&A, tax, interest, capex and principal as positive expenses/outlays; investing/financing cash flows use cash signs. Change in NWC is closing less opening.

CAPM/WACC use the signed treasury policy. Discount each annual FCFF at year-end (1–5) or midyear (0.5–4.5) as signed. Terminal at FY2030 close; perpetuity grows last FCFF by g, exit method uses final EBITDA. Equity value is EV plus FY2025 cash less FY2025 debt. Divide by TSM diluted shares.

## Delivery contract
Inputs!B4:B6 must be editable numeric values stored in the exact underlying units below (display formatting is optional), and downstream formulas must respond dynamically to edits:
- Inputs!B4 (`price_multiplier`): dimensionless decimal multiplier (e.g., `1.0`).
- Inputs!B5 (`dso_shift`): additive shift in calendar days (e.g., `0.0`).
- Inputs!B6 (`risk_free`): annual decimal fraction (e.g., 320 bp MUST be stored as `0.032`, not `320` or `3.2`; display as `3.20%` is optional).
Other inputs and helper tabs may be laid out freely.

Formula scope: every required computed forecast cell in Statements!C4:G33 EXCEPT row 8 (exogenous Cash operating expense, which may either link to a budget sheet or hold the numeric EUR millions budget value), plus every required output in DCF!B4:B9 (and DCF!B12:B15 where requested), MUST be a live Excel formula referencing upstream computation cells (hardcoded numbers, constant-only formulas such as `=1.13`, or bare links to hardcoded helper cells are rejected).

Statements!B3:G3 must be the numeric years 2025–2030. Row numbers below denote outputs in that sheet. In B (actuals) only rows 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 22, 23, 24, 25 are required. C:G require every row. Each row name below is also the requested metric definition. Balance-sheet assets are cash + receivables + inventory + net PP&E, liabilities and equity are AP + debt + equity.

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

DCF sheet outputs (rates such as WACC in B4 must evaluate to annual decimal fractions, e.g., `0.0827` for 8.27%):
- B4: WACC
- B5: Terminal value at FY2030 end
- B6: PV of terminal value
- B7: Enterprise value
- B8: Equity value
- B9: Value per diluted share

Numeric tolerance: greater of EUR million (or native-unit) absolute 0.000001 and 0.0001% relative. Scoring follows a practitioner four-pillar rubric: three-statement & FCFF accuracy (40%), materiality-weighted valuation bridge & per-share value (25%), base & post-shock accounting reconciliation (15%), and assumption sensitivity delta linkage across the three editable assumptions (20%), multiplied by an anti-hardcoding dynamic formula gate.

Additional required outputs (included in the 155 graded live-formula cells): DCF!B12 = relevered equity beta; DCF!B13 = diluted shares (millions); DCF!B14 = median unlevered peer beta; DCF!B15 = TSM incremental shares (millions). All four must resolve to live upstream calculation formulas. Their base values and formulas are graded as part of valuation.
