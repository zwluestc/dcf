# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **27.03%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **271 bp**; equity risk premium (ERP): **627 bp**; pre-tax cost of debt: **551 bp**.
- Statutory corporate tax rate: **22.84%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Maple**: observed equity beta = 0.9391742106885370834213860695, net debt / equity = 0.54x, statutory tax rate = 23%.
- [APPROVED PEER] **Beryl**: observed equity beta = 1.455786744468153018169267336, net debt / equity = 0.56x, statutory tax rate = 27%.
- [APPROVED PEER] **Dune**: observed equity beta = 1.034118611347848687449712953, net debt / equity = 0.29x, statutory tax rate = 22%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Tarmac (LBO Private)**: observed equity beta = 2.567, net debt / equity = 1.97x, statutory tax rate = 25%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **11.61%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **year-end** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **exit EBITDA** (going-concern perpetuity growth mandate = **2.43%**; exit EBITDA multiple assumption = **8.35x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
