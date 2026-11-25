# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **20.99%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **349 bp**; equity risk premium (ERP): **578 bp**; pre-tax cost of debt: **556 bp**.
- Statutory corporate tax rate: **23.79%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

- [APPROVED PEER] **Dune**: observed equity beta = 1.350496685620777505079416743, net debt / equity = 0.29x, statutory tax rate = 26%.
- [EXCLUDED — DISTRESSED / NON-COMPARABLE] **Marrow (Pre-Revenue)**: observed equity beta = 2.2789, net debt / equity = 1.63x, statutory tax rate = 25%.
- [APPROVED PEER] **Slate**: observed equity beta = 1.509150180857212906500829276, net debt / equity = 0.39x, statutory tax rate = 29%.
- [APPROVED PEER] **Haven**: observed equity beta = 1.672450115138652807036454852, net debt / equity = 0.34x, statutory tax rate = 22%.
- [APPROVED PEER] **Linden**: observed equity beta = 1.349500456985717784573407884, net debt / equity = 0.38x, statutory tax rate = 19%.
- [APPROVED PEER] **Birch**: observed equity beta = 1.329379903346802274400675349, net debt / equity = 0.6x, statutory tax rate = 21%.

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **1.0**; editable additive shift to budget collection days (DSO shift): **0.0** days.
- Annual net PP&E depreciation rate: **14.43%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **year-end** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **exit EBITDA** (going-concern perpetuity growth mandate = **1.81%**; exit EBITDA multiple assumption = **9.23x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
