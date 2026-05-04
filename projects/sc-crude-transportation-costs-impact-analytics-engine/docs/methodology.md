# Crude Oil Exposure Quantification — Methodology

## Purpose

This document defines the analytical methodology and data requirements for quantifying **Apex HVAC Global's** exposure to crude oil price shocks across its supply chain. The goal is **decision support analytics**: given a defined crude price shock (e.g., +$10/bbl Brent sustained), produce a defensible, time-phased view of cost impact across the company's freight network — by lane, lane type (inbound/outbound/service/intra-region), mode, and contract type.

### The company being modeled

**Apex HVAC Global** is a synthetic representation of a major global manufacturer of heating, ventilation, air conditioning, and refrigeration (HVAC-R) equipment. The company:

- Operates manufacturing plants in NAM (US), MEX (Mexico), CHN (China), EU (Europe), and ISC (India)
- Distributes finished equipment globally to NAM, EU, MEA, LATAM, CHN, SEA, and ISC markets
- Procures components globally — primarily from CHN, SEA, ISC, and intra-region suppliers
- Operates a global service parts network supporting installed equipment with rapid international distribution
- Has approximately $1.2B in annual transportation spend (synthetic but representative scale)

This is a manufacturer, not a logistics provider. Apex HVAC is the **shipper** (buyer of transportation services); they contract with logistics providers (airlines, shipping lines, trucking companies, 3PLs) to move their inbound components and outbound finished goods.

### Why crude oil exposure matters specifically for a manufacturer

The strategic implication of crude shocks is more severe for a manufacturer than for a third-party logistics provider:

- A logistics provider can adjust pricing upward and pass costs through to its customers
- A manufacturer like Apex HVAC has **already sold** most of its planned production at fixed prices. When delivery costs rise mid-cycle, that increase compresses margin directly on already-booked revenue. There is no immediate pricing lever.

This is why the CEO of an HVAC manufacturer cares deeply about crude-shock exposure: every $/bbl move in Brent ripples through to delivered cost on equipment that was priced six months ago, and the margin compression hits the next quarter's earnings before any pricing action can offset it.

### The transmission model

The methodology is structured as a **four-layer transmission model**. A crude price shock propagates through:

1. **Layer A** - Crude → Refined Product price shock
2. **Layer B** - Refined Product → Lane-level fuel cost (computed bottom-up from physics × activity × price)
3. **Layer C** - Validation bridge between Layer B's computed fuel cost and the company-given total transportation cost (via the implied fuel share, with fallback protocol for outliers)
4. **Layer D** - Provider contract pass-through (determines what Apex absorbs vs. what the logistics provider absorbs)

Each layer has its own data inputs, its own propagation lag, and its own assumptions. The transmission model is the composition of all four layers.

**On what's input vs. what's computed:** total annual transportation cost per lane is **given input** in `lanes.csv` (representing what Apex would pull from its transportation management and financial systems). The lane-level fuel cost is **computed** from physics (sub-mode consumption rate × volume × distance × refined product price). Layer C reconciles the two by checking that the implied fuel share lands within the mode's expected band; lanes outside the band trigger a fallback protocol. This bottom-up approach uses company data as ground truth and uses physics to attribute the fuel portion within it.

### Lane types - a manufacturer-specific concept

Unlike a third-party logistics provider whose "lanes" are simply origin-destination pairs, a manufacturer's freight network has structurally different categories of flow. Apex HVAC's lanes are tagged by `lane_type`:

- **`inbound_component`** — supplier region → manufacturing plant. Production-critical flows. Disruption risks plant stoppage. Mix of ocean (bulk components), air (urgent or expensive parts), and truck (cross-border supplier flows).
- **`outbound_finished`** — manufacturing plant → distribution center / market. Volume-driven flows. Margin-compression risk under shock. Mix of ocean (overseas markets), truck (continental distribution), with limited air.
- **`service_parts`** — central depot → regional service depot. After-sales support flows. Disproportionately air freight; disproportionately spot or short-cycle contracts because urgency dominates cost optimization. Small in tonnage but large in cost-per-ton-km.
- **`intra_region_distribution`** — within-region last-mile distribution from regional DC to local markets. High-frequency, short-distance, almost entirely truck (often shorthaul).

Each lane_type produces different decisions and faces different vulnerabilities. The dashboard surfaces these separately because "your inbound exposure is concentrated on 3 lanes" is a fundamentally different conversation from "your service parts exposure is structurally high."

---

## Layer A - Crude → Refined Product

### What this layer represents

A change in crude oil prices does not translate 1:1 to changes in jet fuel, marine bunker fuel, or diesel. The relationship between crude and refined product prices is governed by the **crack spread** — the difference between the price of a refined product and the price of the crude oil from which it is produced. Crack spreads vary by product, region, and time, reflecting refining capacity, demand patterns, regulation (e.g., IMO 2020 for marine fuels), and seasonality.

For exposure analytics, we need two things from this layer:

1. **A propagation coefficient**: for a $1/bbl change in Brent, how much does the refined product price change in $/bbl-equivalent (or $/MT, or $/gallon)?
2. **A market lag**: how long does it take for a crude price move to be reflected in spot refined product prices?

We are explicitly **not modeling** the crack spread as a stochastic variable. For deterministic shock analysis at v1, we assume the crack spread holds at its long-run average level. The propagation coefficient captures the direct price linkage; we hold the spread constant and let crude move.

### How the propagation coefficient works

Refined product prices generally move directionally with crude, but **not 1:1**. The relationship is captured by a price elasticity coefficient that varies by product.

Empirical research using econometric techniques (vector error correction, wavelet correlation, and impulse response models on multi-decade EIA/Platts price series) consistently finds that:

- **Most refined product elasticities to crude fall in the 0.7-0.9 range.** A 10% change in crude typically produces a 7-9% change in the refined product price. The shortfall reflects non-crude cost components (refining processes, logistics, regulatory compliance) that buffer the price relationship.
- **Fuel oil (the basis for marine bunker) is the closest to unity (≈ 0.95)** because residual fuel requires the fewest post-distillation processing steps. It is essentially crude minus the more valuable distillate cuts, so its price tracks crude very closely.
- **Diesel/middle distillates show high elasticity (≈ 0.90)** due to highly liquid spot markets, simple processing requirements, and direct exposure to crude through the heating-oil/diesel commodity complex.
- **Jet fuel is slightly less elastic (≈ 0.85)** because jet has stricter specifications (kerosene specs, contaminant limits, anti-icing additives) and a separately-traded crack market with its own supply-demand dynamics.

For v1 we adopt these three differentiated coefficients (jet 0.85, diesel 0.90, bunker 0.95). They are research-defensible and they correctly produce the analytical insight that **bunker (ocean) is the most crude-elastic and jet (air) is the least crude-elastic per dollar of crude move** — which matters because it partially counteracts the physics-based intuition that air is more exposed than ocean.

We hold these coefficients constant under a deterministic shock — i.e., we assume crack spreads return to their long-run mean over the analysis horizon and do not separately model crack spread compression or expansion. This is consistent with sustained shock analysis where crack spreads have time to mean-revert. Short-burst scenarios where compression dominates are out of scope for v1.

Two additional modifiers we deliberately do *not* model in v1:

- **Regional basis**: Singapore jet, Rotterdam bunker, and US Gulf diesel all have basis differentials to the global benchmark. For a global company, we use representative regional indices but apply a single global coefficient per product. Regional refinement is a v2 enhancement.
- **Asymmetric pass-through**: Some research finds prices rise faster than they fall ("rockets and feathers"). For a sustained-up-shock scenario like the one we're modeling (geopolitical tension elevating crude), this asymmetry doesn't materially change results. v2 enhancement.

### Unit handling: $/bbl shock to $/MT product price

The user specifies a shock as `ΔBrent` in $/bbl. The propagation to each refined product, in $/MT terms, is:

`Δproduct_price_$/MT = elasticity × ΔBrent_$/bbl × (baseline_product_$/MT / baseline_brent_$/MT)`

where baseline_brent_$/MT = baseline_brent_$/bbl ÷ 0.136 (using ~7.33 bbl/MT for crude density).

This formulation correctly handles the elasticity as a *percentage* relationship — a 10% move in crude produces a (10% × elasticity) move in the product. It also avoids dimensional issues that arise from assuming a $/bbl-to-$/bbl coefficient when products are denser or lighter than crude.

In the data, we therefore store the **elasticity** (a unitless coefficient) plus the **baseline price per MT** for each product. The engine combines these with the shocked Brent price to produce the shocked product price.

### Unit handling

Crude is priced in $/bbl globally. Refined products are variously priced in $/bbl, $/MT, $/gallon, or cents/gallon depending on market convention. To keep the data model clean, we standardize **internal prices to $/MT (metric ton)**, using these density-based conversions:

- 1 bbl Brent ≈ 0.136 MT (using ~7.33 bbl per MT for crude oil density)
- 1 bbl jet fuel ≈ 0.125 MT (~8.0 bbl/MT)
- 1 bbl diesel ≈ 0.131 MT (~7.65 bbl/MT)
- 1 bbl residual fuel oil (bunker basis) ≈ 0.157 MT (~6.35 bbl/MT)

The user specifies the shock in $/bbl Brent (the natural unit). The engine handles the conversion. All lane-level cost computations downstream are in $/MT × MT consumed.

These conversion factors are documented as constants and are not user-configurable. They are physical properties of the fuels.

### Baseline pricing — current market context (April 2026)

The baseline prices in `crude_to_refined.csv` reflect **current market conditions as of April 2026**. The geopolitical environment (Israel-Iran conflict and Strait of Hormuz disruption) has elevated crude and refined product prices significantly above their 2024-25 averages:

- **Brent**: ~$104/bbl (vs. $70-80 historical norm) — elevated due to Strait of Hormuz disruption restricting Persian Gulf flows.
- **Jet fuel**: ~$209/bbl (vs. $90 historical norm) — sharply elevated due to refinery dislocations and middle distillate tightness.
- **Diesel (ULSD)**: ~$170/bbl ≈ $1,300/MT — elevated, reflecting the same middle-distillate squeeze.
- **VLSFO (bunker)**: ~$725/MT — elevated but less so, since residual fuel demand has been somewhat insulated by IMO 2020 dynamics.

These are the **baseline** prices in our model — i.e., "today's market." A shock simulation models *additional* moves beyond these elevated levels (e.g., +$15/bbl on top of the current $104). This framing matches the case context: the CEO is asking precisely because crude is already elevated and could move further.

A return to normalcy (e.g., conflict de-escalation reducing Brent to $80) would itself be a downside scenario in our framework — a *negative* Brent shock, which the engine handles symmetrically.

### Market lag

The market lag captures the time between a sustained crude price move and that move being reflected in spot refined product prices. Empirically (from EIA and IEA price series), this is short — typically 1-3 weeks — because refined product markets are liquid and traders arbitrage spreads quickly.

We use the following lags for v1:

- Jet fuel: 2 weeks
- Diesel: 1 week
- Bunker (residual fuel): 3 weeks

These reflect: jet fuel pricing being slightly slower due to airline contract structures, diesel being the most liquid and fastest, and bunker being slowest due to the physical nature of marine fuel supply chains.

These lags are sourced from typical industry observation, not a specific empirical study. They should be treated as defensible defaults that an analyst can override.

### Data source and update cadence

In a real engagement, the propagation coefficients and lags would be derived from:

- **EIA (US Energy Information Administration)** — daily/weekly crude and refined product price series, publicly available
- **IEA (International Energy Agency)** — global oil market reports, monthly
- **Platts / Argus** — commercial pricing services for spot refined product prices (subscription)
- **Industry pricing reports** — IATA Jet Fuel Monitor for jet, Ship & Bunker for marine bunker, EIA for US diesel
- **Academic research** — peer-reviewed econometric studies of crude-to-product price transmission (e.g., PricePedia 2025 elasticity analysis, ScienceDirect price transmission studies)

For this exercise, the elasticity values are research-based defaults representing typical long-run relationships. The baseline prices should be updated whenever the market context shifts materially (e.g., resolution of the Israel-Iran conflict would warrant repricing the baselines downward).

### Assumptions documented for Layer A

1. Elasticities are differentiated per product (jet 0.85, diesel 0.90, bunker 0.95) based on published econometric research.
2. Elasticities are held constant — we do not model crack spread compression or expansion separately.
3. Regional basis differentials are ignored — a single global elasticity per refined product is used.
4. Market lags are integer weeks — sub-weekly propagation is not modeled.
5. The shock is sustained — we are not modeling brief spikes that revert within days.
6. Pass-through is symmetric — a price drop propagates the same way as a rise (no "rockets and feathers" asymmetry).
7. Density conversions for $/bbl ↔ $/MT use representative averages and are treated as physical constants.
8. Baseline prices reflect April 2026 market conditions (war-elevated). Shocks are layered on top of these baselines.

### Required CSV: `crude_to_refined.csv`

**Schema:**

| Column                    | Type    | Description                                                       | Required |
|---------------------------|---------|-------------------------------------------------------------------|----------|
| refined_product           | string  | Name of refined product (jet / diesel / bunker)                   | Yes      |
| elasticity                | float   | Elasticity of refined product price to crude (unitless, 0-1)      | Yes      |
| market_lag_weeks          | int     | Weeks for crude move to fully reflect in refined product spot     | Yes      |
| bbl_per_mt                | float   | Conversion factor: barrels per metric ton                         | Yes      |
| baseline_price_usd_per_mt | float   | Reference baseline price of refined product in $/MT (April 2026)  | Yes      |
| notes                     | string  | Source, caveats, last review date                                 | No       |

A separate constant `BASELINE_BRENT_USD_PER_BBL = 104.0` is documented in the methodology and consumed by the loader/engine. It represents the reference Brent price (April 2026 spot) against which both refined product baselines are paired and against which user-defined shocks are computed.

**Validation rules:**

- `refined_product` must be one of: `jet`, `diesel`, `bunker`. No other values permitted in v1.
- `elasticity` must be > 0 and ≤ 1.2 (sanity bound — elasticities above 1.2 are inconsistent with empirical research on crude-product price transmission).
- `market_lag_weeks` must be an integer between 0 and 12.
- `bbl_per_mt` must be > 0.
- `baseline_price_usd_per_mt` must be > 0. This is used as the reference price for lane fuel cost computation in Layer B.
- The CSV must contain exactly 3 rows — one per refined product. No duplicates, no missing products.
- Every refined product referenced in `sub_modes.csv` (Layer B) must exist in this CSV.

### How Layer A is used downstream

For a user-defined shock of `ΔBrent` ($/bbl), and using `BASELINE_BRENT_USD_PER_BBL` as the reference:

1. For each refined product `p`:
   - The percentage move in Brent is `pct_move = ΔBrent / BASELINE_BRENT_USD_PER_BBL`
   - The percentage move in product `p` is `pct_move × elasticity_p`
   - The new product price is `shocked_price_p = baseline_price_p × (1 + pct_move × elasticity_p)`
2. The market lag determines when this shocked price applies — at week ≥ market_lag_weeks, the shocked price is in effect; before that, the baseline price applies.

Worked example: `ΔBrent = +$15/bbl` on a $104 baseline is +14.4% in Brent.
- Jet (elasticity 0.85): +12.3% → from $1,672/MT baseline to ~$1,877/MT
- Diesel (elasticity 0.90): +13.0% → from $1,300/MT baseline to ~$1,469/MT
- Bunker (elasticity 0.95): +13.7% → from $725/MT baseline to ~$824/MT

Note that this is *percentage-based* propagation, not $-per-$ propagation. This correctly captures the empirical research and avoids the dimensional inconsistency that arises when crude (in $/bbl) is naively added to product prices (often in $/MT or $/gal).

This propagation feeds Layer B, where the shocked fuel price is multiplied against fuel consumption physics and lane activity to derive lane-level fuel cost impact.

---

## Layer B — Refined Product → Lane-level Fuel Cost

### What this layer represents

Layer A gives us the shocked price of jet, diesel, and bunker. Layer B converts that price into a **lane-level fuel cost in dollars** by combining three things:

1. **Fuel consumption physics** — how much fuel a given equipment type burns per unit of freight movement (e.g., kg jet fuel per ton-km of widebody air freight). This is engineering, not economics.
2. **Lane activity** — how much freight moves on each lane (annual volume in tons, distance in km).
3. **The current refined product price** — from Layer A's `baseline_price_usd_per_mt`, optionally shocked.

The output is a dollar figure per lane: *this is how much fuel cost is embedded in lane X's annual transportation cost.* This number is then used in two ways:

- **Validation**: compared against the given annual transportation cost to derive implied fuel share, which should land in industry-realistic ranges as a sanity check.
- **Sensitivity computation**: shocked vs. baseline fuel cost on each lane gives the gross fuel exposure, which feeds Layer D.

Layer B is also where **procurement lag** lives — the lag between a spot refined product price moving and the company's actual paid fuel cost moving. This is distinct from market lag (Layer A) and contract lag (Layer D).

### Two-level mode hierarchy: mode and sub-mode

Real freight networks operate diverse equipment within each broad mode of transport. A wide-body freighter and a narrow-body freighter both fall under "air" but have dramatically different fuel intensities per ton-km. The same is true for ULCVs vs. feeder vessels in ocean, and for long-haul vs. short-haul trucking.

To capture this realistically without conflating different concepts, we use a **two-level hierarchy**:

- **Mode** (air / ocean / truck) — carries *market-structure properties* that hold across all equipment within the mode. Specifically: procurement lag and the expected fuel-share-of-transportation-cost range. These reflect how the fuel market behaves for that mode (hedging norms, inventory holding, surcharge cadence) and are largely independent of which specific equipment is used.

- **Sub-mode** (e.g., air_widebody, ocean_feeder) — carries *equipment-level properties*. Specifically: fuel type used and consumption rate per ton-km. These are physical/engineering properties of the equipment.

Each lane references a sub-mode. Its mode is derived through the hierarchy. A lane on `air_widebody` has the air mode's procurement lag and the widebody equipment's consumption rate.

This separation is conceptually cleaner than putting everything in one table, and it prevents accidentally varying procurement lag by equipment type when only consumption should vary.

### The seven sub-modes

We define seven sub-modes covering the realistic range of global freight equipment:

**Air (2 sub-modes):**
- **`air_widebody`** — long-haul international freight (777F, 747-8F equivalents). Consumption rate ~0.45 kg jet fuel per ton-km. The efficient workhorse for transcontinental and transoceanic air freight.
- **`air_narrowbody`** — regional/short-haul air freight (737F, A321F equivalents). Consumption rate ~0.70 kg jet fuel per ton-km. Higher fuel intensity per ton-km because takeoff/climb is a larger share of the flight, and these aircraft carry less per trip.

**Ocean (3 sub-modes):**
- **`ocean_ulcv`** — Ultra-Large Container Vessels (18,000+ TEU). Consumption rate ~0.010 kg bunker per ton-km. Extreme economies of scale; deployed on the busiest trunk routes (Asia-Europe, transpacific main).
- **`ocean_panamax`** — mid-size container ships (4,000-10,000 TEU). Consumption rate ~0.018 kg bunker per ton-km. Workhorse for secondary trade lanes.
- **`ocean_feeder`** — small container ships (<3,000 TEU). Consumption rate ~0.030 kg bunker per ton-km. Used for regional connectivity and shallow-port routes.

**Truck (2 sub-modes):**
- **`truck_longhaul`** — interstate or cross-border, fully loaded tractor-trailer at highway speeds. Consumption rate ~0.025 kg diesel per ton-km.
- **`truck_shorthaul`** — regional or last-mile, smaller trucks, urban-rural mix, partial loads. Consumption rate ~0.045 kg diesel per ton-km. Higher fuel intensity due to stop-and-go driving, less optimal loading factors, and smaller equipment.

The intra-mode ratios are realistic and consequential for the analytics:
- Air narrowbody is ~1.5× more fuel-intensive than widebody
- Ocean feeder is ~3× more fuel-intensive than ULCV
- Truck shorthaul is ~1.8× more fuel-intensive than longhaul

These ratios mean that within a mode, sub-mode choice can swing fuel exposure significantly. A lane operated on ocean feeder is meaningfully more crude-exposed than the same lane operated on ULCV — a real-world insight that the analytics surfaces directly.

The cross-mode ratios remain dramatic (air widebody ≈ 30× ocean ULCV per ton-km). This is the dominant driver of why air freight is much more crude-exposed than ocean — it is *physically* far more fuel-intensive per unit of work performed.

### Why these numbers are public knowledge — and the source landscape

Sub-mode-level consumption coefficients are not commercially sensitive. They appear in:

- **IATA fuel efficiency reports** — fleet- and aircraft-type-level fuel burn statistics for air freight
- **IMO and Clarksons Research** — vessel-class-level fuel consumption data for shipping (ULCV, Panamax, feeder breakdowns are standard)
- **US EPA SmartWay, EU CLECAT reports, and ATRI** — truck fuel efficiency benchmarks by equipment class and operation type
- **ICCT (International Council on Clean Transportation)** — peer-reviewed analyses across all freight modes and sub-types

In a real engagement, an analyst would cite specific sources for the chosen coefficients. For this exercise, we use representative averages with the source landscape documented above.

### Procurement lag — the second time dimension

When a refined product spot price moves, the company's *actual paid fuel cost* does not move immediately. There are several reasons:

- **Inventory** — providers hold fuel inventory bought at prior prices. This buffers short-term moves.
- **Hedging** — airlines and shipping lines often hedge a portion of forward fuel needs. A company dealing with an airline whose Q3 fuel is 50% hedged sees only half the spot move flow through.
- **Supply contracts** — fuel supply contracts with airports, ports, and fuel distributors have weekly, monthly, or quarterly resets rather than daily spot pricing.
- **Operational reset cadence** — the cadence at which the company's payments to its providers reflect new fuel prices.

We model these collectively as a **procurement lag in weeks per mode** — stored at the mode level, not the sub-mode level, because these are market-structure properties that hold across equipment within a mode.

For v1:

- **Air**: 2 weeks. Airline fuel costs adjust relatively quickly through monthly fuel surcharge resets and limited inventory holdings (jet fuel inventory at airports is typically a few days, not weeks).
- **Ocean**: 4 weeks. Bunker fuel pricing adjusts more slowly due to longer voyage cycles, larger fuel inventories aboard vessels, and hedging programs typical at major shipping lines.
- **Truck**: 1 week. Diesel pricing is highly liquid; trucking companies pass spot diesel changes through fuel surcharges that often reset weekly.

The total time from a Brent shock to a lane's fuel cost actually being affected is therefore: **market lag (Layer A) + procurement lag (Layer B)**. For an air lane, that's 2 + 2 = 4 weeks regardless of whether it's widebody or narrowbody. For ocean, 3 + 4 = 7 weeks. For truck, 1 + 1 = 2 weeks. This staircase of lags is what produces the time-phased impact view that distinguishes our analytics from a flat sensitivity number.

### How lane fuel cost is computed

For each lane in `lanes.csv`:

1. **Identify sub-mode** → look up consumption rate and fuel type from `sub_modes.csv`.
2. **Identify mode** → derived through `sub_modes.csv` foreign key to `modes.csv`. Used for procurement lag and expected fuel share range.
3. **Identify fuel type** → look up baseline price from `crude_to_refined.csv`.
4. **Compute annual fuel consumption (MT)**:
   `fuel_mt = annual_volume_tons × distance_km × consumption_rate_kg_per_ton_km / 1000`
5. **Compute annual fuel cost ($)**:
   `fuel_cost_usd = fuel_mt × baseline_price_usd_per_mt`
6. **Shocked fuel cost** uses the shocked price from Layer A in step 5.

The same formula applies across modes and sub-modes; only the coefficients change.

### Validation against given transportation cost — and the fallback mechanism

Each lane in `lanes.csv` carries an `annual_transportation_cost_usd` field — what the company actually pays to logistics providers for that lane. The implied **fuel share** is:

`fuel_share = computed_fuel_cost / annual_transportation_cost_usd`

This should land within the mode's expected range (defined in `modes.csv`). The bands below are wider than typical "average" figures because real-world fuel shares vary substantially by lane configuration, equipment type, region, and current fuel price levels:

- **Air: 22-40%** — IATA economic data shows jet fuel typically accounts for 25-30% of airline operating costs but can exceed 40% during volatile periods. Lower bound 22% allows for newer, more fuel-efficient widebody freighters on long-haul routes; upper bound 40% allows for narrowbody or short-haul lanes during high-fuel-price periods.
- **Ocean: 20-50%** — published figures range widely. Industry sources cite "as much as 50-60%" of ship operating costs for total fuel, while transportation cost figures (the relevant denominator for our model) typically run 20-40%. Lower bound 20% allows for ULCVs on efficient trunk routes; upper bound 50% allows for feeder vessels and high-fuel-price periods.
- **Truck: 18-40%** — ATRI puts US trucking fuel at 20-30% of operating costs; international sources (e.g., MBIE for NZ heavy vehicles) cite 35-40%. Lower bound 18% allows for efficient long-haul on flat terrain; upper bound 40% allows for short-haul, urban, or cross-border with high diesel prices.

These bands are intentionally permissive because the alternative — tight bands that fire warnings on every other lane — would render the validation useless. The bands flag genuinely anomalous lanes, not minor variation.

If a lane's computed fuel share falls outside its mode's expected range by more than **7 percentage points** (the validation tolerance), the loader applies the following protocol:

1. **Log a warning** with the lane ID, computed fuel share, expected range, and the most likely cause (e.g., "computed fuel share 50% exceeds expected air range 22-40% by >7pp; possible causes include over-stated annual volume, under-stated transportation cost, or wrong sub-mode assignment").
2. **Apply a fallback fuel cost** that lands the fuel share at the *midpoint* of the mode's expected range:
   `fallback_fuel_cost = annual_transportation_cost × (expected_share_min + expected_share_max) / 2`
3. **Tag the lane** with a `fuel_cost_source` attribute equal to either `"physics_computed"` (default) or `"fallback_midpoint"` (when the fallback is applied).
4. **Propagate the tag** so downstream outputs can transparently flag which lanes are using fallback values. The CEO-facing summary should be able to report something like "5 of 47 lanes are using fallback fuel share because physics-based computation was outside the expected range."

The fallback ensures the analytics never crashes or produces nonsense numbers, but it never silently hides data quality issues. The warning is loud, the fallback is conservative (midpoint), and the tag ensures the issue is visible all the way through to the decision-support output.

The 7pp tolerance is calibrated based on observed spread of fuel-share figures in industry research (different sources reporting the same mode at values 5-10pp apart, depending on methodology, region, and time period). 7pp gives breathing room for legitimate variation while still catching genuine data errors.

For synthetic data populated to specification, we should expect zero warnings — if any fire, the synthetic data is internally inconsistent and must be fixed.

The fuel share itself is **computed**, not stored. It is an output of the model and a validation signal, not an input.

### Assumptions documented for Layer B

1. Within each sub-mode, fuel consumption is treated as a constant — we do not differentiate by aircraft age, vessel build year, truck model year, or other within-class variation.
2. Distance × volume × consumption rate is a linear approximation — we ignore non-linearities like takeoff/landing fuel for short air lanes, port maneuvering for ocean, or terrain for truck.
3. The 12 tons-per-TEU conversion for ocean is an assumed average across cargo types. Lightweight (high cubic) and heavyweight (dense) cargo would convert differently in reality.
4. Procurement lag is mode-level and constant — we do not vary it by region, by individual provider hedging programs, or by sub-mode.
5. Fuel consumed = fuel paid for. We ignore fuel theft, technical losses, and reporting discrepancies. These are typically <2% of total fuel and would be lost in the precision of the sensitivity analysis.
6. Empty-leg/backhaul imbalances are not modeled. Fuel is computed against full-load equivalent ton-km; in reality, return legs may run partially empty, raising effective fuel-per-paid-ton-km. Out of scope for v1.
7. Speed/slow-steaming variability for ocean is not modeled. Vessels operate at a single representative speed embedded in the consumption coefficient. Out of scope for v1.

### Required CSV: `modes.csv`

**Schema:**

| Column                       | Type   | Description                                                          | Required |
|------------------------------|--------|----------------------------------------------------------------------|----------|
| mode                         | string | Mode of transport (air / ocean / truck)                              | Yes      |
| procurement_lag_weeks        | int    | Weeks between refined product price move and paid fuel cost move     | Yes      |
| expected_fuel_share_min      | float  | Lower bound of expected fuel-as-%-of-transportation-cost (decimal)   | Yes      |
| expected_fuel_share_max      | float  | Upper bound of expected fuel-as-%-of-transportation-cost (decimal)   | Yes      |
| notes                        | string | Source, caveats, last review date                                    | No       |

**Validation rules:**

- `mode` must be one of: `air`, `ocean`, `truck`. No other values permitted in v1.
- `procurement_lag_weeks` must be an integer between 0 and 12.
- `expected_fuel_share_min` must be ≥ 0 and < `expected_fuel_share_max`.
- `expected_fuel_share_max` must be ≤ 0.6 (60% — anything higher would be unrealistic).
- The CSV must contain exactly 3 rows — one per mode. No duplicates, no missing modes.
- Every mode referenced in `sub_modes.csv` must exist in this CSV.

### Required CSV: `sub_modes.csv`

**Schema:**

| Column                       | Type   | Description                                                          | Required |
|------------------------------|--------|----------------------------------------------------------------------|----------|
| sub_mode                     | string | Equipment class identifier (e.g., air_widebody, ocean_feeder)        | Yes      |
| mode                         | string | Parent mode (air / ocean / truck) — foreign key to `modes.csv`       | Yes      |
| fuel_type                    | string | Refined product consumed — foreign key to `crude_to_refined.csv`     | Yes      |
| consumption_kg_per_ton_km    | float  | Fuel consumption rate in kg per ton-km                               | Yes      |
| description                  | string | Plain-English description of the equipment class                     | No       |
| notes                        | string | Source, caveats, last review date                                    | No       |

**Validation rules:**

- `sub_mode` must be unique across rows. No duplicates.
- `sub_mode` values used in `lanes.csv` must all exist in this CSV (foreign key integrity).
- `mode` must exist in `modes.csv` (foreign key integrity).
- `fuel_type` must exist as a `refined_product` in `crude_to_refined.csv` (foreign key integrity).
- All sub-modes within a given mode must use the same `fuel_type` (e.g., both air sub-modes use jet; air_widebody using diesel would be invalid).
- `consumption_kg_per_ton_km` must be > 0 and < 5.0 (sanity bound — anything higher implies an unreasonable consumption rate).
- The CSV must contain exactly 7 rows in v1: 2 air, 3 ocean, 2 truck. Future expansion is allowed by adding rows; missing any of the 7 named sub-modes is an error.

### How Layer B is used downstream

For each lane, Layer B produces:

1. **Baseline annual fuel cost** ($) — used as the reference point. May be physics-computed or fallback-midpoint depending on validation outcome.
2. **Shocked annual fuel cost** ($) — under a user-defined Brent shock. Uses the same source basis (physics or fallback) as the baseline, scaled by the price shock.
3. **Gross fuel exposure** ($) = shocked − baseline. This is the dollar amount of additional fuel cost the company-plus-provider-system absorbs annually under the shock, before any contract pass-through.
4. **Combined lag** (weeks) = market_lag (Layer A) + procurement_lag (Layer B). This is when the gross fuel exposure starts hitting the company's paid fuel cost.
5. **Fuel cost source tag** — `"physics_computed"` or `"fallback_midpoint"`. Carried through all downstream outputs so data quality is always traceable.

These five items per lane feed Layer D, which determines what portion of the gross exposure the company actually absorbs (vs. is absorbed by the logistics provider) based on the contract archetype on that lane.

---

## Layer D — Provider Contract Pass-through

### What this layer represents

Layers A, B, and C tell us how much *more fuel cost* enters the company-plus-provider system under a shock. Layer D tells us how that increase is *split between the company and the logistics provider* over time — and that split is what determines the company's net P&L exposure.

The contract is between the **company** (Apex HVAC) and the **logistics provider** (airline, shipping line, trucking company). The contract specifies — implicitly or explicitly — how fuel cost changes flow from the provider to the company. This is the **upstream** contract, not a customer-facing surcharge contract.

The terms of this contract determine:

- **What share of a fuel cost increase the provider can pass to the company** (pass-through %)
- **How long it takes for that pass-through to take effect** (contract lag in weeks)

A high pass-through, short lag contract leaves the company highly exposed to fuel shocks — the provider will quickly reflect higher fuel costs in what they charge the company. A low pass-through, long lag contract insulates the company in the short run — the provider absorbs the cost. Fixed contracts insulate the company completely until the contract is renewed.

This is counterintuitive but correct: a company whose lanes are mostly on Fixed and BAF (Bunker Adjustment Factor) contracts is *less* short-term-exposed to a sustained fuel shock than a company whose lanes are mostly on Spot. The trade-off is that the insulating contracts typically cost more upfront. Decision support analytics surfaces both sides of this trade-off; the recommendation layer (out of v1 scope) is where this would be acted on.

### The five contract archetypes

We define five archetypes covering the realistic spectrum of provider contracts in global freight. Each is characterized by a pass-through percentage and a contract lag in weeks.

**Archetype 1 — `spot`**
- Pass-through: 95%
- Contract lag: 1 week
- Description: The company books capacity at the spot rate. Spot rates already embed current fuel prices, so pass-through is effectively immediate on the next booking. The 1-week lag reflects the time between the shock reaching the spot market and the company's next booking. Common in trucking spot markets and air freight spot bookings.

**Archetype 2 — `indexed_short`**
- Pass-through: 90%
- Contract lag: 2 weeks
- Description: Fuel surcharge clauses indexed to a public diesel or fuel index, resetting weekly or bi-weekly. The provider passes most of the move to the company within two weeks. Common in trucking with DOE-indexed fuel surcharges.

**Archetype 3 — `indexed_medium`**
- Pass-through: 80%
- Contract lag: 4 weeks
- Description: Monthly fuel surcharge resets indexed to a published fuel benchmark. The provider absorbs short-term volatility but passes through sustained moves. Common in air freight and contracted trucking with monthly resets.

**Archetype 4 — `baf_long`**
- Pass-through: 70%
- Contract lag: 12 weeks
- Description: Bunker Adjustment Factor (BAF) clauses with quarterly resets. The provider absorbs short-term volatility for an extended period; pass-through is partial reflecting the negotiated split of fuel cost risk. Common in ocean freight contracts with shipping lines.

**Archetype 5 — `fixed`**
- Pass-through: 0%
- Contract lag: not applicable (modeled as 999 weeks for the engine, denoting beyond the analysis horizon)
- Description: Long-term capacity commitment with no fuel adjustment during the contract term. The provider fully absorbs fuel risk in exchange for a higher base rate. Common in enterprise capacity agreements where the company or the provider has chosen to lock in a price.

These five archetypes are deliberately a small closed set. Real contracts have more variation, but five archetypes capture the dominant patterns and produce a model whose behavior is interpretable. Adding more archetypes would increase synthetic data complexity without adding analytical clarity.

### Pass-through and lag are simplifications — what they collapse

Real contracts have two separate timing concepts that we are deliberately collapsing into a single lag:

- **Reset cadence** — how often the contract's surcharge value is recalculated (weekly, monthly, quarterly).
- **Lookback window** — what historical price data the recalculation uses (e.g., previous week's average, previous month's average, etc.).

In v1, we collapse both into a single `contract_lag_weeks` parameter representing the *effective* delay between a sustained shock and the contract fully reflecting it. This is conservative for shock analysis — it under-estimates the absorption period at the start (because lookbacks delay things further) and over-estimates how quickly steady-state pass-through is reached. For a sustained shock over 8+ weeks, the simplification is acceptable. For short-burst shocks that revert before contracts reset, this simplification understates company insulation. We are explicitly out of scope for short-burst shocks.

We also deliberately ignore:

- **Caps** on per-period surcharge changes (some contracts limit how much the surcharge can move per reset). Caps would extend the apparent lag for large shocks — a v2 enhancement.
- **Floors** on minimum surcharge values (some contracts have minimum fuel rates regardless of crude). Floors matter for downside scenarios (crude crash) — out of scope for upward-shock analysis.
- **Renegotiation events** that might trigger off-cycle. We assume contracts hold their terms across the analysis horizon.

### Lane-contract assignment — splits across multiple providers

A lane is rarely served by a single provider on a single contract. In practice:

- A high-volume transpacific lane might use 60% one shipping line on a BAF contract, 30% another on a different BAF contract, and 10% spot bookings.
- An air freight lane might split between scheduled airline capacity (indexed_medium) and chartered capacity (spot).
- A trucking lane might split between contracted providers (indexed_short) and brokered capacity (spot).

To model this realistically, `lane_contracts.csv` allows each lane to have multiple rows, each specifying a provider, a contract archetype, and a **share of lane volume** (a decimal between 0 and 1). The shares for any given lane must sum to exactly 1.0.

This produces a **blended exposure** at the lane level — a weighted average of pass-through percentages across the providers serving the lane, with each provider's contract lag applied to its share of the lane's gross fuel exposure.

For a lane split 60% baf_long / 40% spot:

- 60% of the gross fuel exposure follows the baf_long timing (70% pass-through, 12 week lag)
- 40% of the gross fuel exposure follows the spot timing (95% pass-through, 1 week lag)
- Blended steady-state pass-through = 0.60 × 70% + 0.40 × 95% = 80%
- The time-phased absorption is the sum of the two pieces, each on its own staircase

The time-phased view becomes a **superposition of staircases** rather than a single staircase, which more accurately reflects how a real company's net exposure unfolds.

### How Layer D produces the company's net exposure

For each lane, given the gross fuel exposure (from Layer B) and the lane's contract mix (from Layer D), the company's net exposure unfolds as follows over time. Let:

- `t_market` = market_lag from Layer A (depends on fuel type)
- `t_proc` = procurement_lag from Layer B (depends on mode)
- `t_contract` = contract_lag for a given contract archetype
- `pt` = pass-through % for that archetype
- `share` = share of lane volume on that contract
- `gross` = annual gross fuel exposure on the lane (from Layer B)

For each (lane, contract-archetype-on-the-lane) combination, three windows describe the time-phased absorption:

- **Weeks 0 to (t_market + t_proc):** The shock has not yet reached the company's paid fuel cost. Neither party absorbs anything — the contracted rate has not changed. Net company exposure is zero.
- **Weeks (t_market + t_proc) to (t_market + t_proc + t_contract):** The fuel cost has hit the provider, but the contract has not yet reset. The provider is bearing the full cost increase; the company is still paying its pre-shock contracted rate. Net company exposure during this window is **zero**; provider absorption is `share × gross`.
- **Weeks ≥ (t_market + t_proc + t_contract):** The contract has reset and now reflects (most of) the higher fuel cost in what the company pays the provider. Net company exposure on this share-of-lane reaches steady state at `pt × share × gross`. The remaining `(1 − pt) × share × gross` continues to be absorbed by the provider indefinitely.

This produces the key insight that distinguishes well-contracted networks from poorly-contracted ones: **the company is insulated during the entire pre-contract-reset window**. The provider takes the hit. After the contract resets, the company absorbs `pass-through × gross` (the steady-state company net), and the provider continues to absorb `(1 − pass-through) × gross` indefinitely (or until the next contract renegotiation).

The time-phased view per lane is therefore:

- A flat zero from week 0 through the combined market+procurement lag
- Still flat zero until the contract resets (provider takes the hit during this window)
- A step up to `pass-through × gross` once the contract resets

For a lane with multiple contracts (split shares), each share has its own staircase, and the lane-level total at any time is the sum across shares.

### Assumptions documented for Layer D

1. Only five contract archetypes exist in v1. Real-world contracts not falling cleanly into one archetype must be approximated.
2. Pass-through and contract lag are constants per archetype — no variation by region, provider, or contract size.
3. Reset cadence and lookback window are collapsed into a single contract_lag_weeks value.
4. Caps and floors on surcharge values are not modeled.
5. Contract terms hold constant across the full analysis horizon — no renegotiation, no contract expiration.
6. The provider absorbs all costs during the pre-contract-reset window. We do not model the provider attempting to renegotiate, withdraw capacity, or default during this window. In extreme sustained shocks, real providers do exit unprofitable contracts — out of scope for v1.
7. Pass-through % is symmetric — applies the same way to upward and downward shocks. Real contracts sometimes have asymmetric pass-through (faster increases than decreases), but symmetric is the v1 simplification.

### Required CSV: `contract_archetypes.csv`

**Schema:**

| Column                       | Type   | Description                                                                  | Required |
|------------------------------|--------|------------------------------------------------------------------------------|----------|
| archetype                    | string | Archetype identifier (spot / indexed_short / indexed_medium / baf_long / fixed) | Yes   |
| pass_through_pct             | float  | Share of fuel cost change passed from provider to company (decimal 0 to 1)  | Yes      |
| contract_lag_weeks           | int    | Weeks for the contract to fully reflect a sustained price move               | Yes      |
| description                  | string | Plain-English description of the archetype                                   | No       |
| notes                        | string | Source, caveats, last review date                                            | No       |

**Validation rules:**

- `archetype` must be one of: `spot`, `indexed_short`, `indexed_medium`, `baf_long`, `fixed`. No other values permitted in v1.
- `archetype` must be unique across rows. No duplicates.
- `pass_through_pct` must be ≥ 0 and ≤ 1.
- `contract_lag_weeks` must be an integer ≥ 0. For the `fixed` archetype, this is set to 999 to denote a lag beyond the analysis horizon; the engine treats this as "never resets within the modeled period."
- The CSV must contain exactly 5 rows — one per archetype. No duplicates, no missing archetypes.
- Every archetype referenced in `lane_contracts.csv` must exist in this CSV (foreign key integrity).

### How Layer D is used downstream

For each lane, Layer D combined with prior layers produces:

1. **Blended steady-state pass-through** (decimal) — weighted average of pass-through % across the lane's contract mix.
2. **Company net steady-state exposure** ($) — `blended_pass_through × gross_fuel_exposure`. This is what the company pays the providers in increased contracted rates once all contracts have reset. The remaining `(1 − blended_pass_through) × gross` is absorbed by the providers indefinitely (or until contract renewal).
3. **Time-phased exposure curve** — for each week from 0 to the analysis horizon, the company's cumulative net exposure. Constructed as the sum of staircases across all (lane × contract) combinations.
4. **First-impact week** — earliest week at which the company sees any non-zero net exposure on the lane.
5. **Steady-state week** — week at which the company's net exposure on the lane stabilizes (the latest contract reset across the lane's contract mix).
6. **Provider absorption curve** — mirror image. The provider absorbs the gross exposure during the pre-reset window, and `(1 − pass-through) × gross` indefinitely thereafter. Useful as a sanity check (gross = company net steady-state + provider absorption steady-state).

These outputs, aggregated across the network, produce the four diagnostic outputs identified in the original framing: sensitivity table, exposure concentration, pass-through reality check, and comparative mode view.

---

## Network Data — `region_anchors.csv`, `lanes.csv`, and `lane_contracts.csv`

The three network CSVs are synthetic but structured as if they were extracted from Apex HVAC Global's transportation management and financial systems. They are populated to specification rather than researched.

### Required CSV: `region_anchors.csv`

This CSV defines the geographic anchor (representative city + lat/long) for each region used in the network. The flow map dashboard uses these coordinates to plot inter-regional lanes; lane references in `lanes.csv` resolve to coordinates via this table.

The single-anchor-per-region simplification means that when a lane spans (for example) NAM to LATAM, the rendered flow line goes from the NAM anchor (a representative US city) to the LATAM anchor (São Paulo), regardless of which specific origin/destination drove the flow. This is acceptable for continental-scale visualization. A v2 enhancement would split large regions like NAM into east/west sub-anchors.

**Schema:**

| Column        | Type   | Description                                                  | Required |
|---------------|--------|--------------------------------------------------------------|----------|
| region_code   | string | Region identifier (e.g., NAM, MEX, EU)                       | Yes      |
| anchor_city   | string | Representative city name for visualization labels            | Yes      |
| latitude      | float  | Latitude of anchor city in decimal degrees                   | Yes      |
| longitude     | float  | Longitude of anchor city in decimal degrees                  | Yes      |
| description   | string | Brief description of the region's role in Apex HVAC's network | No      |

**Validation rules:**

- `region_code` must be unique across rows.
- `latitude` must be between -90 and 90.
- `longitude` must be between -180 and 180.
- The CSV must contain exactly 8 rows in v1: NAM, MEX, EU, CHN, ISC, SEA, MEA, LATAM.
- Every region referenced in `lanes.csv` (origin_region or destination_region) must exist in this CSV.

### Required CSV: `lanes.csv`

**Schema:**

| Column                          | Type   | Description                                                          | Required |
|---------------------------------|--------|----------------------------------------------------------------------|----------|
| lane_id                         | string | Unique lane identifier (e.g., L001, L002...)                         | Yes      |
| origin_region                   | string | Origin region code — foreign key to `region_anchors.csv`             | Yes      |
| destination_region              | string | Destination region code — foreign key to `region_anchors.csv`        | Yes      |
| lane_type                       | string | Type of flow (inbound_component / outbound_finished / service_parts / intra_region_distribution) | Yes |
| sub_mode                        | string | Equipment sub-mode — foreign key to `sub_modes.csv`                  | Yes      |
| distance_km                     | float  | One-way lane distance in kilometers                                  | Yes      |
| annual_volume_tons              | float  | Annual freight volume in metric tons                                 | Yes      |
| annual_transportation_cost_usd  | float  | Annual amount Apex HVAC pays providers for this lane (USD)           | Yes      |

**Validation rules:**

- `lane_id` must be unique across rows. No duplicates.
- `origin_region` and `destination_region` must exist in `region_anchors.csv`.
- `lane_type` must be one of: `inbound_component`, `outbound_finished`, `service_parts`, `intra_region_distribution`.
- For `lane_type = intra_region_distribution`: `origin_region` MUST equal `destination_region` (this lane type is by definition within-region).
- For `lane_type = inbound_component`: `origin_region` may equal `destination_region` (intra-region supplier-to-plant flows) or differ (overseas supplier-to-plant flows). Both are valid.
- For `lane_type = outbound_finished`: `origin_region` may equal `destination_region` (plant-to-regional-DC flows within a region) or differ (plant-to-overseas-market flows). Both are valid.
- For `lane_type = service_parts`: `origin_region` may equal `destination_region` (central depot to regional service depot within a region) or differ (cross-continent service parts distribution). Both are valid.
- `sub_mode` must exist in `sub_modes.csv` (foreign key integrity).
- `distance_km` must be > 0 and < 30,000 (sanity bound — longest realistic freight lane is ~25,000 km for round-the-world ocean).
- `annual_volume_tons` must be > 0.
- `annual_transportation_cost_usd` must be > 0.
- Every lane_id must appear at least once in `lane_contracts.csv` (no orphan lanes).

Internal sanity checks (warnings, not errors) executed by the loader:

- Computed fuel share by lane should fall within `[expected_fuel_share_min, expected_fuel_share_max]` of the lane's mode (per Layer B's fallback protocol).
- The total network annual transportation cost should be consistent with a major global HVAC manufacturer — flagged if implausibly small (<$300M) or large (>$3B) for the configured number of lanes.

### Required CSV: `lane_contracts.csv`

**Schema:**

| Column                       | Type   | Description                                                                  | Required |
|------------------------------|--------|------------------------------------------------------------------------------|----------|
| lane_id                      | string | Lane identifier — foreign key to `lanes.csv`                                | Yes      |
| provider_name                | string | Name of the logistics provider (free-form; e.g., "Provider A")              | Yes      |
| contract_archetype           | string | Archetype identifier — foreign key to `contract_archetypes.csv`             | Yes      |
| share_of_lane_volume         | float  | Share of the lane's volume served by this provider/contract (decimal 0 to 1) | Yes      |

**Validation rules:**

- `lane_id` must exist in `lanes.csv` (foreign key integrity).
- `contract_archetype` must exist in `contract_archetypes.csv` (foreign key integrity).
- `share_of_lane_volume` must be > 0 and ≤ 1.
- For each `lane_id`, the sum of `share_of_lane_volume` across all rows must equal 1.0 (within a tolerance of 0.001 to allow for rounding).
- A lane may have between 1 and 5 contract rows (1 = single provider, 5 = highly fragmented; more than 5 is implausible at this level of modeling).
- The combination of (`lane_id`, `provider_name`) must be unique — a single provider does not serve the same lane on two different contracts simultaneously in v1.

Internal sanity checks (warnings, not errors):

- Across the entire network, the distribution of contract archetypes should be plausible — flagged if any archetype represents 0% or >70% of total contracted volume (suggests synthetic data is too uniform or too skewed).
- High-volume lanes (top 20% by annual_volume_tons) should typically not be 100% spot — flagged if a top lane is fully spot, since real shippers contract their highest-volume lanes.

---

## Cross-CSV Integrity Summary

The following foreign key relationships and global constraints must hold across the data set. These are validated by the loader and are the comprehensive integrity guarantee for the data model.

**Foreign keys:**

1. `sub_modes.fuel_type` → `crude_to_refined.refined_product`
2. `sub_modes.mode` → `modes.mode`
3. `lanes.sub_mode` → `sub_modes.sub_mode`
4. `lanes.origin_region` → `region_anchors.region_code`
5. `lanes.destination_region` → `region_anchors.region_code`
6. `lane_contracts.lane_id` → `lanes.lane_id`
7. `lane_contracts.contract_archetype` → `contract_archetypes.archetype`

**Global constraints:**

1. Every mode in `modes.csv` must be referenced by at least one sub-mode in `sub_modes.csv`.
2. Every sub-mode in `sub_modes.csv` must be referenced by at least one lane in `lanes.csv` (no orphan sub-modes).
3. Every lane in `lanes.csv` must have at least one entry in `lane_contracts.csv` (no orphan lanes).
4. For every lane, the contract shares must sum to exactly 1.0.
5. All sub-modes within a given mode must use the same fuel type (e.g., all air sub-modes use jet).
6. `lane_type` must be one of the four prescribed values; only `intra_region_distribution` lanes are *required* to have origin = destination. All other lane types may have either same-region or cross-region origin/destination depending on the realistic flow being modeled.
7. The CSVs must contain the exact prescribed number of rows where specified: 3 refined products, 3 modes, 7 sub-modes, 5 contract archetypes, 8 region anchors. The lane and lane_contract CSVs are open-ended in row count.

This integrity layer is the answer to the requirement that data be complete with no insufficiency and no circular errors. The loader will fail loudly with a precise error message on any violation.
