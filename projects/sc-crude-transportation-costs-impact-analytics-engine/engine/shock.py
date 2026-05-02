"""
Shock simulator — Layer 2 of the analytics pipeline.

Given a NetworkDiagnostic (Layer 1) and a Brent shock value (in $/bbl),
computes the time-phased net exposure for the company across the network.

The math follows methodology Layer A + B + D:

  1. Crude shock (delta_brent) propagates to each refined product price using
     the elasticity from crude_to_refined.csv:
        new_product_price = baseline * (1 + delta_brent / baseline_brent * elasticity)

  2. For each lane, fuel cost shocks linearly with refined product price:
        fuel_cost_shocked = annual_fuel_cost * (new_price / baseline_price)
        gross_fuel_exposure = fuel_cost_shocked - annual_fuel_cost

  3. Combined market+procurement lag determines when the shock first reaches
     the company-plus-provider system on a lane:
        first_system_impact_week = market_lag + procurement_lag

  4. For each (lane, contract-share) pair:
        - Weeks 0 to (first_system_impact_week + contract_lag): company net
          exposure = 0. Provider absorbs the cost.
        - Weeks >= (first_system_impact_week + contract_lag):
            company_net_share_exposure = pass_through * share * gross_exposure
            provider_share_residual    = (1 - pass_through) * share * gross_exposure
            (provider absorbs the residual indefinitely)

  5. The lane-level time-phased curve is the sum across contract shares.
     The network-level curve is the sum across lanes.

All values are expressed as ANNUALIZED dollars at steady-state (the shock is
sustained and the analysis horizon is long enough for all contracts to reset).
The week-by-week curve shows when each piece of that annualized exposure
*starts hitting* the company — not a cash-flow projection at weekly granularity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .loader import NetworkData, BASELINE_BRENT_USD_PER_BBL
from .network import NetworkDiagnostic


# Default analysis horizon: 26 weeks (two quarters), covers all v1 contract lags
# except `fixed` (sentinel 999 — never resets within horizon, so company never
# absorbs on those contracts in v1)
DEFAULT_HORIZON_WEEKS = 26


@dataclass
class ShockResult:
    """Output of a shock simulation."""

    delta_brent_usd_per_bbl: float
    horizon_weeks: int

    # Per-refined-product shocked prices ($/MT) and pct moves
    shocked_prices: pd.DataFrame  # columns: refined_product, baseline_price, shocked_price, pct_move

    # Per-lane shock results (one row per lane)
    # Columns: lane_id, ..., gross_fuel_exposure_usd,
    #          company_net_steady_state_usd, provider_absorption_steady_state_usd,
    #          first_company_impact_week, steady_state_week
    lanes: pd.DataFrame

    # Network totals
    total_gross_exposure_usd: float
    total_company_net_steady_state_usd: float
    total_provider_absorption_steady_state_usd: float

    # Time-phased curves
    # network_curve: indexed by week 0..horizon, value = cumulative company
    #                net exposure ($) hitting by that week
    network_curve: pd.Series
    # by_mode_curve: same shape, columns = air/ocean/truck (stacked area)
    by_mode_curve: pd.DataFrame
    # by_lane_type_curve: columns = inbound/outbound/service/intra
    by_lane_type_curve: pd.DataFrame
    # by_archetype_curve: columns = spot/indexed_short/indexed_medium/baf_long/fixed
    by_archetype_curve: pd.DataFrame
    # by_sub_mode_curve: columns = air_widebody/air_narrowbody/ocean_ulcv/...
    by_sub_mode_curve: pd.DataFrame
    # Per-lane share contributions for drill-down:
    #   lane_id -> [{provider, archetype, share_company_net, flip_week,
    #                share_of_volume, pass_through}, ...]
    lane_share_contributions: dict

    # First-impact and steady-state weeks at the network level
    first_company_impact_week: int
    steady_state_week: int

    # Insight metrics for auto-text
    top_5_lanes_share_of_company_net: float  # how concentrated the exposure is
    top_lane_id: str
    top_lane_company_net_usd: float


def compute_shock(
    network: NetworkData,
    diagnostic: NetworkDiagnostic,
    delta_brent_usd_per_bbl: float,
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
) -> ShockResult:
    """Apply a sustained Brent shock to the network and return time-phased results.

    Parameters
    ----------
    network : NetworkData (used for crude_to_refined and lane_contracts)
    diagnostic : NetworkDiagnostic (provides per-lane Layer 1 data)
    delta_brent_usd_per_bbl : the sustained Brent move ($/bbl). Positive = up.
    horizon_weeks : analysis horizon (default 26)
    """
    # --- 1. Compute shocked refined product prices ---
    crude = network.crude_to_refined.copy()
    pct_brent_move = delta_brent_usd_per_bbl / BASELINE_BRENT_USD_PER_BBL
    crude["pct_move"] = pct_brent_move * crude["elasticity"]
    crude["shocked_price_usd_per_mt"] = (
        crude["baseline_price_usd_per_mt"] * (1 + crude["pct_move"])
    )
    shocked_prices = crude[[
        "refined_product", "elasticity", "baseline_price_usd_per_mt",
        "shocked_price_usd_per_mt", "pct_move", "market_lag_weeks",
    ]].copy()

    # Build a fuel_type -> (baseline_price, shocked_price, pct_move) lookup
    fuel_pct_move = dict(zip(crude["refined_product"], crude["pct_move"]))

    # --- 2. Per-lane gross fuel exposure ---
    lanes = diagnostic.lanes.copy()
    lanes["fuel_pct_move"] = lanes["fuel_type"].map(fuel_pct_move)
    lanes["gross_fuel_exposure_usd"] = (
        lanes["annual_fuel_cost_usd"] * lanes["fuel_pct_move"]
    )

    # --- 3. Per-lane: company net steady-state and provider absorption ---
    # Steady-state = after all contracts on the lane have reset.
    # company_net = pass_through * gross
    # provider_absorption = (1 - pass_through) * gross
    lanes["company_net_steady_state_usd"] = (
        lanes["blended_pass_through"] * lanes["gross_fuel_exposure_usd"]
    )
    lanes["provider_absorption_steady_state_usd"] = (
        (1.0 - lanes["blended_pass_through"]) * lanes["gross_fuel_exposure_usd"]
    )

    # --- 4. First company impact week per lane ---
    # = combined market+procurement lag + blended contract lag
    # But blended_contract_lag is a weighted average; for week-by-week curves we
    # need the per-share-of-lane staircase, not the average. We compute both:
    #   - lanes['first_company_impact_week'] = combined_lag + min(per-lane-contract-lags)
    #   - lanes['steady_state_week']         = combined_lag + max(per-lane-contract-lags)
    contracts = network.lane_contracts.merge(
        network.contract_archetypes, left_on="contract_archetype", right_on="archetype"
    )
    # Replace the 999 sentinel for fixed contracts with horizon+1 — outside the
    # analysis window, so they never contribute to within-horizon company exposure
    contracts["effective_contract_lag"] = contracts["contract_lag_weeks"].clip(
        upper=horizon_weeks + 1
    )

    first_impact_per_lane = []
    steady_state_per_lane = []
    for lane_id in lanes["lane_id"]:
        lane_contracts = contracts[contracts["lane_id"] == lane_id]
        combined = int(
            lanes.loc[lanes["lane_id"] == lane_id, "combined_lag_weeks"].iloc[0]
        )
        # First impact is when the *fastest* contract resets (any reset triggers
        # company exposure on that share)
        # Skip contracts with pass-through = 0 (fixed): they never produce company
        # exposure regardless of timing
        non_zero_pt = lane_contracts[lane_contracts["pass_through_pct"] > 0]
        if non_zero_pt.empty:
            # All contracts are fixed -> no company exposure within horizon
            first_impact_per_lane.append(horizon_weeks + 1)
            steady_state_per_lane.append(horizon_weeks + 1)
        else:
            first_impact_per_lane.append(
                combined + int(non_zero_pt["effective_contract_lag"].min())
            )
            steady_state_per_lane.append(
                combined + int(non_zero_pt["effective_contract_lag"].max())
            )
    lanes["first_company_impact_week"] = first_impact_per_lane
    lanes["steady_state_week"] = steady_state_per_lane

    # --- 5. Build time-phased curves ---
    # We compute the *cumulative* company net exposure that has "started hitting"
    # by week w. Each (lane, contract-share) flips on at its specific reset week.
    weeks = np.arange(horizon_weeks + 1)
    network_curve_values = np.zeros(len(weeks))

    # Per-mode curves
    modes_present = ["air", "ocean", "truck"]
    by_mode_values = {m: np.zeros(len(weeks)) for m in modes_present}

    # Per-lane-type curves
    lane_types_present = list(lanes["lane_type"].unique())
    by_lane_type_values = {lt: np.zeros(len(weeks)) for lt in lane_types_present}

    # Per-archetype curves (NEW for Page 4)
    archetypes_present = ["spot", "indexed_short", "indexed_medium", "baf_long", "fixed"]
    by_archetype_values = {a: np.zeros(len(weeks)) for a in archetypes_present}

    # Per-sub-mode curves (NEW for Page 4)
    sub_modes_present = list(lanes["sub_mode"].unique())
    by_sub_mode_values = {sm: np.zeros(len(weeks)) for sm in sub_modes_present}

    # Per-lane-share contributions (NEW for Page 4 drill-down):
    # lane_id -> list of (provider_name, archetype, share_company_net, flip_week)
    lane_share_contributions: dict[str, list] = {}

    # Build an iterable of (lane_id, gross, mode, lane_type, share, pt, contract_lag)
    lane_meta = lanes.set_index("lane_id")
    for _, contract in contracts.iterrows():
        lane_id = contract["lane_id"]
        if lane_id not in lane_meta.index:
            continue
        lane = lane_meta.loc[lane_id]
        gross = float(lane["gross_fuel_exposure_usd"])
        share = float(contract["share_of_lane_volume"])
        pt = float(contract["pass_through_pct"])
        contract_lag = int(contract["effective_contract_lag"])
        combined_lag = int(lane["combined_lag_weeks"])
        flip_week = combined_lag + contract_lag
        archetype = contract["contract_archetype"]
        provider = contract["provider_name"]

        share_company_net = pt * share * gross

        # Always record the lane share (even if flip outside horizon — for drill-down)
        lane_share_contributions.setdefault(lane_id, []).append({
            "provider": provider,
            "archetype": archetype,
            "share_company_net": share_company_net,
            "flip_week": flip_week,
            "share_of_volume": share,
            "pass_through": pt,
        })

        if flip_week > horizon_weeks:
            continue  # Outside horizon; doesn't contribute to curves

        # Cumulative: this share's company-net exposure "starts hitting" at flip_week
        # and remains thereafter. So we add `share_company_net` to all weeks >= flip_week.
        network_curve_values[flip_week:] += share_company_net
        by_mode_values[lane["mode"]][flip_week:] += share_company_net
        by_lane_type_values[lane["lane_type"]][flip_week:] += share_company_net
        by_archetype_values[archetype][flip_week:] += share_company_net
        by_sub_mode_values[lane["sub_mode"]][flip_week:] += share_company_net

    network_curve = pd.Series(network_curve_values, index=weeks, name="company_net_usd")
    by_mode_curve = pd.DataFrame(by_mode_values, index=weeks)
    by_mode_curve.index.name = "week"
    by_lane_type_curve = pd.DataFrame(by_lane_type_values, index=weeks)
    by_lane_type_curve.index.name = "week"
    by_archetype_curve = pd.DataFrame(by_archetype_values, index=weeks)
    by_archetype_curve.index.name = "week"
    by_sub_mode_curve = pd.DataFrame(by_sub_mode_values, index=weeks)
    by_sub_mode_curve.index.name = "week"

    # --- 6. Network totals ---
    total_gross = float(lanes["gross_fuel_exposure_usd"].sum())
    total_company_net = float(lanes["company_net_steady_state_usd"].sum())
    total_provider_absorb = float(lanes["provider_absorption_steady_state_usd"].sum())

    # First company impact and steady state at the network level
    # (only consider lanes with non-zero gross exposure)
    nonzero_lanes = lanes[lanes["gross_fuel_exposure_usd"].abs() > 0.01]
    if len(nonzero_lanes) == 0 or delta_brent_usd_per_bbl == 0:
        net_first_impact = 0
        net_steady = 0
    else:
        # First impact: earliest non-zero on the curve (excluding all-fixed lanes
        # where first_company_impact_week was set to horizon+1)
        within_horizon = lanes[lanes["first_company_impact_week"] <= horizon_weeks]
        if within_horizon.empty:
            net_first_impact = 0
            net_steady = 0
        else:
            net_first_impact = int(within_horizon["first_company_impact_week"].min())
            net_steady = int(within_horizon["steady_state_week"].min())
            # steady_state at network level = max over within-horizon lanes
            net_steady = int(within_horizon["steady_state_week"].max())

    # --- 7. Insight metrics ---
    if delta_brent_usd_per_bbl != 0 and total_company_net != 0:
        sorted_lanes = lanes.sort_values(
            "company_net_steady_state_usd", ascending=False, key=abs
        )
        top_5_share = float(
            sorted_lanes.head(5)["company_net_steady_state_usd"].sum() / total_company_net
        )
        top_lane_row = sorted_lanes.iloc[0]
        top_lane_id = str(top_lane_row["lane_id"])
        top_lane_company_net = float(top_lane_row["company_net_steady_state_usd"])
    else:
        top_5_share = 0.0
        top_lane_id = ""
        top_lane_company_net = 0.0

    return ShockResult(
        delta_brent_usd_per_bbl=delta_brent_usd_per_bbl,
        horizon_weeks=horizon_weeks,
        shocked_prices=shocked_prices,
        lanes=lanes,
        total_gross_exposure_usd=total_gross,
        total_company_net_steady_state_usd=total_company_net,
        total_provider_absorption_steady_state_usd=total_provider_absorb,
        network_curve=network_curve,
        by_mode_curve=by_mode_curve,
        by_lane_type_curve=by_lane_type_curve,
        by_archetype_curve=by_archetype_curve,
        by_sub_mode_curve=by_sub_mode_curve,
        lane_share_contributions=lane_share_contributions,
        first_company_impact_week=net_first_impact,
        steady_state_week=net_steady,
        top_5_lanes_share_of_company_net=top_5_share,
        top_lane_id=top_lane_id,
        top_lane_company_net_usd=top_lane_company_net,
    )
