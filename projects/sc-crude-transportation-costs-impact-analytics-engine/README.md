# Apex HVAC Global — Crude Oil Exposure Intelligence Engine

A decision-support analytics platform that quantifies a global HVAC manufacturer's
exposure to sustained crude oil price shocks across its freight network — by lane,
mode, lane type, contract archetype, and provider — and shows how that exposure
unfolds in time as contracts reset.

This project uses a synthetic company called **Apex HVAC Global** that mirrors
the operational profile of a major global HVAC and refrigeration manufacturer:
multinational manufacturing footprint, complex inbound component sourcing,
outbound finished-goods distribution, urgency-driven service-parts air freight,
and last-mile distribution to dealers and contractors. All data is generated
synthetically; no real company data is used.

This is a **decision-support tool**, not a recommender — it surfaces and
quantifies the question rather than auto-generating action plans.

---

## What problem does this solve?

A senior leader at a global HVAC manufacturer asks:

> *"If Brent moves from $104 to $120 and stays there, what does that cost us, when does it hit, and where is the exposure concentrated?"*

There is no off-the-shelf answer. Spot price moves do not translate 1-for-1 to
delivered cost; refined product elasticities, fuel-consumption physics, mode
mix, contract archetypes, provider concentration, and reset cadences all shape
the answer. This engine assembles those pieces into a coherent, time-phased
view of company-level exposure.

The strategic stakes are different for a manufacturer than for a third-party
logistics provider. A logistics provider can raise prices and pass fuel costs
through to its customers. A manufacturer like Apex HVAC has **already sold**
most of its planned production at fixed prices — when delivery costs rise
mid-cycle, that increase compresses margin directly on already-booked revenue.
There is no immediate pricing lever.

---

## How it works — the four-layer transmission model

A crude price shock propagates through the network in four layers:

- **Layer A — Crude → Refined Product.** Brent moves do not propagate 1:1 to
  jet fuel, diesel, or bunker. We use research-defensible elasticities (jet
  0.85, diesel 0.90, bunker 0.95) and per-product market lags (1-3 weeks).

- **Layer B — Refined Product → Lane-level Fuel Cost.** Computed bottom-up
  from physics × activity × price: each sub-mode has a consumption coefficient
  (kg fuel per ton-km), each lane has volume × distance, and the shocked
  product price is applied. Adds a per-mode procurement lag (1-4 weeks)
  reflecting inventory, hedging, and supply contract cadences.

- **Layer C — Validation Bridge.** The given annual transportation cost is
  the ground truth. Computed fuel cost should land within the mode's expected
  fuel-share band (air 22-40%, ocean 20-50%, truck 18-40%) within a ±7pp
  tolerance. Lanes outside the band trigger a fallback protocol that uses
  the band midpoint, with a transparent tag preserved through every
  downstream output.

- **Layer D — Provider Contract Pass-through.** Five contract archetypes
  (spot, indexed_short, indexed_medium, baf_long, fixed) determine what share
  of the gross fuel cost increase the transportation provider passes to the
  company, and with what lag. A spot contract passes 95% within a week; a
  fixed contract passes 0% indefinitely. Each lane can be split across
  multiple providers on different archetypes.

The total time from a Brent shock to a lane's *company net* exposure stepping
up is therefore: **market lag (A) + procurement lag (B) + contract lag (D)**.
That staircase produces the time-phased dynamics the dashboard surfaces.

---

## Architecture

```
crude_exposure/
├── desktop_app/                                # PyQt5 desktop UI
│   ├── main.py                                 # Entry point
│   ├── theme.py                                # Bloomberg-style dark theme
│   ├── controller.py                           # Engine state + debounced shock updates
│   ├── main_window.py                          # Sidebar nav + content area + status bar
│   ├── pages/
│   │   ├── page1_executive.py                      # Page 1 container (2 tabs)
│   │   ├── page1_vulnerability_tab.py              # Tab 1.1 — standing diagnostic
│   │   ├── page1_shock_tab.py                      # Tab 1.2 — shock simulator
│   │   ├── page2_lane_flow_map.py                  # Page 2 — world flow map
│   │   ├── page3_exposure_concentration.py         # Page 3 — Pareto + concentration
│   │   ├── page4_time_phased_impact.py             # Page 4 — time dynamics
│   │   └── placeholder.py                          # Pages 5-7 placeholders
│   └── widgets/                                # Reusable QPainter / pyqtgraph widgets
├── engine/                                     # Pure analytics layer (no UI deps)
│   ├── loader.py                                   # CSV reader + integrity validation
│   ├── network.py                                  # Layer 1: standing diagnostic
│   └── shock.py                                    # Layer 2: shock-applied compute
├── data/                                       # 7 CSVs, validated on load
├── scripts/
│   └── generate_network_data.py                # Reproducible synthetic network data
├── docs/
│   ├── methodology.md                              # Full analytical methodology
│   └── REVIEW_GUIDE.md                             # Review checklist
├── requirements.txt
└── README.md (this file)
```

---

## What the dashboard shows

### Page 1 — Executive Summary

**Two tabs.**

*Tab 1.1 — Network Vulnerability Snapshot.* Shock-independent. Answers "where
are we structurally exposed?" Shows total transport cost ($1.06B), total fuel
cost ($333.6M, 32% of transport), network blended pass-through (72%), and the
single number that matters: **structural exposure** (~$94M) — what the company
absorbs at steady state under any sustained upward fuel cost move. Then
decomposes by mode (donut), contract archetype (stacked bar), and lane type
(vertical bars), with a vulnerability fingerprint of 6 compact metrics and an
auto-generated headline insight.

*Tab 1.2 — Shock Impact Simulator.* Shock-dependent. Subscribes to the
sidebar slider. Shows the shocked refined product prices, gross/net/provider
breakdown, the time-phased company-net staircase by mode with reference lines
at first-impact and steady-state weeks, lag distribution histogram, and
top-lane concentration callout.

### Page 2 — Lane Flow Map

Geographic visualization. World map with 8 region anchors (sized by total cost
flowing through), 64 inter-region flow arcs (colored by exposure intensity,
sized by transport cost). Layer toggle between Vulnerability and Shock impact.
Filter chips for modes, lane types, and a "top 25% only" mode. Disruption
hotspots marked at Hormuz, Suez, Panama. Antimeridian-crossing arcs (CHN↔NAM)
split cleanly across the map edges.

### Page 3 — Exposure Concentration

The Pareto question. Top 5 lanes carry ~27% of structural exposure; top 10
carry ~45%; reaching 80% requires ~30 lanes (38% of the network). Centerpiece
is the Pareto curve with marked annotations at top-5/10/25. Below it: a
contract-archetype-mix matrix per lane type (revealing that *service parts*
has 87% blended pass-through — the most fragile category — versus *inbound
component* at 65%, the most insulated), and a provider-concentration table
(top provider carries ~12% of exposure; top 3 carry ~33%).

### Page 4 — Time-Phased Impact

The deep dive on temporal dynamics. Slice selector lets the user pivot the
staircase by mode, lane type, contract archetype, or sub-mode. The archetype
slice is the most analytically illuminating — it shows the temporal hierarchy
directly: spot fires first/small, indexed_short next, indexed_medium dominates
the middle, baf_long fills the late tail. Below the chart: a "early-impact
lanes" table (lanes flipping by week 4 — the actionable renegotiation
candidates) and a lane drill-down that shows any selected lane's
share-by-share staircase, with each provider/archetype combination plotted as
its own area.

Empty state when shock = 0 — page surfaces the prompt rather than silently
showing a flat zero.

### Pages 5-7 — Pending

- Page 5: Pass-Through Reality Check (gross vs net waterfall, insulation)
- Page 6: Mode Comparison (cost-per-ton-km, mode-shift breakeven)
- Page 7: Scenario Library (predefined scenarios + what-if comparisons)

---

## Running locally

### Prerequisites

- Python 3.11 (other 3.10+ versions should also work)
- A virtual environment is recommended

### Setup

```bash
cd crude_exposure
python -m venv venv
# Windows
.\venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python desktop_app/main.py
```

The window opens at 1440×900 by default and resizes.

### Driving the app

The **Δ Brent** slider in the sidebar (-$50 to +$50/bbl) drives every
shock-dependent view. Movement is debounced at 250ms — drag freely; the
recompute fires once the slider settles. Quick-set buttons for common
scenarios:

- **Hormuz +$40** — geopolitical disruption escalation
- **Tension +$15** — moderate sustained tension (default)
- **Ceasefire −$15** — partial de-escalation
- **Reset 0** — return to baseline (unshocked)

The bottom-of-window status bar shows data integrity status, lane/contract
counts, total network cost, and methodology version.

---

## What's deliberately out of scope (v1)

- **Recommendations.** This is decision support, not a recommender. The
  dashboard quantifies the question; humans decide what to do about it.
- **Stochastic crack spreads.** Crack spreads are held at long-run averages.
  A v2 would model crack spread compression/expansion under shock.
- **Asymmetric pass-through.** Real contracts often have rockets-and-feathers
  asymmetry (faster increases than decreases). v1 is symmetric.
- **Customer-facing surcharges.** The company-customer pricing dynamic is out
  of scope; this models only the company-provider contract upstream.
- **Capacity withdrawal under extreme shock.** Real transportation providers
  may exit unprofitable contracts in extreme sustained shocks; v1 assumes
  contracts hold across the analysis horizon.
- **Sub-weekly precision.** All lags are integer weeks.

These are documented assumptions, not silent omissions — see methodology.md
for full assumption disclosures per layer.

---

## Terminology

This project uses two terms consistently:

- **Company** — the manufacturer being modeled (Apex HVAC Global). Where the
  dashboard refers to "company net exposure," "company pays after resets,"
  etc., it means the share of fuel cost that lands on the manufacturer's P&L.
- **Transportation provider** (or just **provider**) — the logistics
  counterparty (a trucking firm, ocean liner, air-freight forwarder) that
  moves the freight on a given lane. Where the dashboard says "provider
  absorbs," it means the share of fuel cost the provider eats indefinitely
  due to contract terms.

We deliberately avoid the word "carrier" because in supply chain English it
typically means the transportation provider, but in financial-modeling
English it can mean the entity exposed to a liability. The disambiguation
matters here.

---

## Status

- ✅ Data model — 7 CSVs, validated
- ✅ Methodology document — ~680 lines
- ✅ Engine — loader, network diagnostic, shock simulator (with archetype/sub-mode curves and per-lane share contributions for drill-down)
- ✅ Desktop app skeleton — sidebar, navigation, theme, debounced shock controller
- ✅ Page 1 — Executive Summary (vulnerability + shock tabs)
- ✅ Page 2 — Lane Flow Map
- ✅ Page 3 — Exposure Concentration (Pareto + archetype matrix + provider concentration)
- ✅ Page 4 — Time-Phased Impact (slice selector + dual chart + lane drill-down)
- 🚧 Page 5 — Pass-Through Reality Check
- 🚧 Page 6 — Mode Comparison
- 🚧 Page 7 — Scenario Library
