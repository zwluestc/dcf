# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **18.67%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **348 bp**; equity risk premium (ERP): **495 bp**; pre-tax cost of debt: **641 bp**.
- Statutory corporate tax rate: **27.14%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Cinder**: observed equity beta = 1.315181301911131773176949856, net debt / equity = 0.52x, statutory tax rate = 26%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Kestrel (Distressed)**: observed equity beta = 2.6538, net debt / equity = 2.04x, statutory tax rate = 25%.
- [APPROVED PEER] **Alder**: observed equity beta = 1.532810682445576700745943227, net debt / equity = 0.59x, statutory tax rate = 22%.
- [APPROVED PEER] **Birch**: observed equity beta = 1.437189651002778149911724023, net debt / equity = 0.26x, statutory tax rate = 20%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **11.4%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **midyear** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **perpetuity** (going-concern perpetuity growth mandate = **1.94%**; exit EBITDA multiple assumption = **8.18x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
