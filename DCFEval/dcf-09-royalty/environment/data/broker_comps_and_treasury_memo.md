# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **18.38%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **396 bp**; equity risk premium (ERP): **572 bp**; pre-tax cost of debt: **620 bp**.
- Statutory corporate tax rate: **23.48%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Dune**: observed equity beta = 1.560586901629582660391702821, net debt / equity = 0.35x, statutory tax rate = 21%.
- [APPROVED PEER] **Flint**: observed equity beta = 1.409674102192483337091522653, net debt / equity = 0.53x, statutory tax rate = 26%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Marrow (Pre-Revenue)**: observed equity beta = 2.1976, net debt / equity = 1.83x, statutory tax rate = 25%.
- [APPROVED PEER] **Birch**: observed equity beta = 1.332956466723470088784400914, net debt / equity = 0.18x, statutory tax rate = 24%.
- [APPROVED PEER] **Cinder**: observed equity beta = 1.404087329853726589594940766, net debt / equity = 0.33x, statutory tax rate = 24%.
- [APPROVED PEER] **Maple**: observed equity beta = 1.901828957730779369873300945, net debt / equity = 0.6x, statutory tax rate = 27%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **11.19%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **midyear** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **perpetuity** (going-concern perpetuity growth mandate = **2.62%**; exit EBITDA multiple assumption = **9.61x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
