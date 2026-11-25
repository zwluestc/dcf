# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **25.68%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **297 bp**; equity risk premium (ERP): **615 bp**; pre-tax cost of debt: **443 bp**.
- Statutory corporate tax rate: **27.38%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Haven**: observed equity beta = 1.391852780183841429151899708, net debt / equity = 0.37x, statutory tax rate = 25%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Kestrel (Distressed)**: observed equity beta = 2.7236, net debt / equity = 1.64x, statutory tax rate = 25%.
- [APPROVED PEER] **Maple**: observed equity beta = 1.275149543004785604669849727, net debt / equity = 0.58x, statutory tax rate = 28%.
- [APPROVED PEER] **Flint**: observed equity beta = 1.631434705846313026079626528, net debt / equity = 0.55x, statutory tax rate = 26%.
- [APPROVED PEER] **Slate**: observed equity beta = 1.511094611733551602937483898, net debt / equity = 0.67x, statutory tax rate = 19%.
- [APPROVED PEER] **Linden**: observed equity beta = 1.741358273471827370588434729, net debt / equity = 0.48x, statutory tax rate = 27%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **11.37%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **midyear** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **exit EBITDA** (going-concern perpetuity growth mandate = **2.08%**; exit EBITDA multiple assumption = **8.43x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
