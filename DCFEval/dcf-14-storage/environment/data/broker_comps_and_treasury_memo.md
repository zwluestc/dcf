# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **36.57%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **334 bp**; equity risk premium (ERP): **503 bp**; pre-tax cost of debt: **617 bp**.
- Statutory corporate tax rate: **20.45%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Dune**: observed equity beta = 0.9931126040792601195604024083, net debt / equity = 0.3x, statutory tax rate = 19%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Tarmac (LBO Private)**: observed equity beta = 2.6054, net debt / equity = 2.19x, statutory tax rate = 25%.
- [APPROVED PEER] **Haven**: observed equity beta = 1.143332386407214717324693462, net debt / equity = 0.23x, statutory tax rate = 27%.
- [APPROVED PEER] **Flint**: observed equity beta = 0.8032879898063621689395543853, net debt / equity = 0.29x, statutory tax rate = 18%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **13.97%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **midyear** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **perpetuity** (going-concern perpetuity growth mandate = **1.61%**; exit EBITDA multiple assumption = **9.08x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
