# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **37.99%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **332 bp**; equity risk premium (ERP): **583 bp**; pre-tax cost of debt: **441 bp**.
- Statutory corporate tax rate: **21.12%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Aster**: observed equity beta = 1.057870364259953671650431797, net debt / equity = 0.64x, statutory tax rate = 26%.
- [APPROVED PEER] **Beryl**: observed equity beta = 0.8869499461671257983777423525, net debt / equity = 0.45x, statutory tax rate = 18%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Marrow (Pre-Revenue)**: observed equity beta = 2.2119, net debt / equity = 1.82x, statutory tax rate = 25%.
- [APPROVED PEER] **Linden**: observed equity beta = 0.6645804124913978038219148821, net debt / equity = 0.3x, statutory tax rate = 29%.
- [APPROVED PEER] **Alder**: observed equity beta = 1.112776151826588075007671524, net debt / equity = 0.51x, statutory tax rate = 26%.
- [APPROVED PEER] **Dune**: observed equity beta = 1.013960817036419037068942123, net debt / equity = 0.2x, statutory tax rate = 29%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **10.28%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **year-end** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **perpetuity** (going-concern perpetuity growth mandate = **2.02%**; exit EBITDA multiple assumption = **9.89x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
