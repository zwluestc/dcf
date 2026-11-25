# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **25.91%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **375 bp**; equity risk premium (ERP): **568 bp**; pre-tax cost of debt: **639 bp**.
- Statutory corporate tax rate: **20.66%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Flint**: observed equity beta = 1.520953060353929465525339346, net debt / equity = 0.45x, statutory tax rate = 20%.
- [APPROVED PEER] **Dune**: observed equity beta = 1.441693374807022397351573574, net debt / equity = 0.64x, statutory tax rate = 26%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Tarmac (LBO Private)**: observed equity beta = 2.3637, net debt / equity = 1.95x, statutory tax rate = 25%.
- [APPROVED PEER] **Alder**: observed equity beta = 1.01691592809508561888399752, net debt / equity = 0.3x, statutory tax rate = 29%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **12.03%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **midyear** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **exit EBITDA** (going-concern perpetuity growth mandate = **2.66%**; exit EBITDA multiple assumption = **7.07x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
