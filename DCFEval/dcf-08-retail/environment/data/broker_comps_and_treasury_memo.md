# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **21.85%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **342 bp**; equity risk premium (ERP): **596 bp**; pre-tax cost of debt: **473 bp**.
- Statutory corporate tax rate: **24.34%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Kestrel (Distressed)**: observed equity beta = 2.6414, net debt / equity = 2.02x, statutory tax rate = 25%.
- [APPROVED PEER] **Aster**: observed equity beta = 1.524538612551040744828119391, net debt / equity = 0.28x, statutory tax rate = 21%.
- [APPROVED PEER] **Dune**: observed equity beta = 1.458357653236300865288554674, net debt / equity = 0.5x, statutory tax rate = 27%.
- [APPROVED PEER] **Maple**: observed equity beta = 1.366110904167763763455476248, net debt / equity = 0.65x, statutory tax rate = 25%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **12.51%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **year-end** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **exit EBITDA** (going-concern perpetuity growth mandate = **2.1%**; exit EBITDA multiple assumption = **10.51x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
