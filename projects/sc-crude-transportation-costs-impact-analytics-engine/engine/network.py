"""
Network diagnostic engine — Layer 1 of the analytics pipeline.

Computes the standing diagnostic of Apex HVAC's network — properties that are
independent of any specific shock. This includes per-lane economics, blended
contract pass-through, fragility scores, and aggregate breakdowns by mode,
sub-mode, lane_type, and contract archetype.

The output of this module feeds both the vulnerability views in the dashboard
(which display these directly) and the shock simulator (which uses them as
inputs to time-phased shock propagation).

All functions are pure: they take a NetworkData object and return a
NetworkDiagnostic object. No mutation, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .loader import NetworkData


@dataclass
class NetworkDiagnostic:
    """The standing diagnostic of the network. Computed once at startup."""

    # Per-lane diagnostic (one row per lane)
    # Columns: lane_id, origin_region, destination_region, lane_type, sub_mode,
    #          mode, distance_km, annual_volume_tons, annual_transportation_cost_usd,
    #          annual_fuel_cost_usd, fuel_share, fuel_cost_source,
    #          blended_pass_through, blended_contract_lag_weeks,
    #          structural_exposure_usd, fuel_intensity_kg_per_ton_km,
    #          high_intensity_flag, market_lag_weeks, procurement_lag_weeks
    lanes: pd.DataFrame

    # Network totals
    total_annual_transportation_cost_usd: float
    total_annual_fuel_cost_usd: float
    total_structural_exposure_usd: float
    network_blended_pass_through: float

    # Time dimension (first-impact week range across the network)
    earliest_first_impact_week: int  # min combined market+procurement lag across lanes
    latest_first_impact_week: int    # max

    # Aggregates by dimension (each is a DataFrame)
    by_mode: pd.DataFrame                # cost, fuel_cost, structural_exposure, lane_count
    by_sub_mode: pd.DataFrame            # ditto, plus consumption rate
    by_lane_type: pd.DataFrame           # ditto by lane_type
    by_archetype_volume: pd.DataFrame    # volume share by contract archetype

    # Vulnerability fingerprint (small named metrics for the dashboard footer)
    fingerprint: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# High-intensity sub-modes per methodology — flagged as structurally penalized
HIGH_INTENSITY_SUB_MODES = {"air_narrowbody", "ocean_feeder", "truck_shorthaul"}


def _compute_blended_pass_through_and_lag(
    lane_id: str, contracts: pd.DataFrame, archetype_lookup: pd.DataFrame
) -> tuple[float, float]:
    """For a single lane, compute blended pass-through and blended contract lag.

    Blending is by share_of_lane_volume.
    """
    lane_contracts = contracts[contracts["lane_id"] == lane_id]
    merged = lane_contracts.merge(
        archetype_lookup, left_on="contract_archetype", right_on="archetype"
    )

    blended_pt = (merged["pass_through_pct"] * merged["share_of_lane_volume"]).sum()
    blended_lag = (merged["contract_lag_weeks"] * merged["share_of_lane_volume"]).sum()

    return float(blended_pt), float(blended_lag)


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_diagnostic(network: NetworkData) -> NetworkDiagnostic:
    """Compute the standing diagnostic of the network."""
    lanes = network.lanes.copy()
    sub_modes = network.sub_modes
    modes = network.modes
    crude = network.crude_to_refined
    archetypes = network.contract_archetypes

    # --- Build lookups for joining ---
    sub_mode_to_mode = dict(zip(sub_modes["sub_mode"], sub_modes["mode"]))
    sub_mode_to_consumption = dict(zip(sub_modes["sub_mode"],
                                       sub_modes["consumption_kg_per_ton_km"]))
    sub_mode_to_fuel = dict(zip(sub_modes["sub_mode"], sub_modes["fuel_type"]))
    mode_to_proc_lag = dict(zip(modes["mode"], modes["procurement_lag_weeks"]))
    fuel_to_market_lag = dict(zip(crude["refined_product"], crude["market_lag_weeks"]))

    # --- Annotate per-lane fields needed for diagnostic ---
    lanes["mode"] = lanes["sub_mode"].map(sub_mode_to_mode)
    lanes["fuel_type"] = lanes["sub_mode"].map(sub_mode_to_fuel)
    lanes["fuel_intensity_kg_per_ton_km"] = lanes["sub_mode"].map(sub_mode_to_consumption)
    lanes["high_intensity_flag"] = lanes["sub_mode"].isin(HIGH_INTENSITY_SUB_MODES)
    lanes["procurement_lag_weeks"] = lanes["mode"].map(mode_to_proc_lag)
    lanes["market_lag_weeks"] = lanes["fuel_type"].map(fuel_to_market_lag)
    lanes["combined_lag_weeks"] = lanes["procurement_lag_weeks"] + lanes["market_lag_weeks"]

    # Rename derived columns from loader for clarity
    lanes["annual_fuel_cost_usd"] = lanes["_annual_fuel_cost_usd"]
    lanes["fuel_share"] = lanes["_fuel_share"]
    lanes["fuel_cost_source"] = lanes["_fuel_cost_source"]

    # --- Compute blended pass-through and contract lag per lane ---
    blended_pt = []
    blended_lag = []
    for lane_id in lanes["lane_id"]:
        pt, lag = _compute_blended_pass_through_and_lag(
            lane_id, network.lane_contracts, archetypes
        )
        blended_pt.append(pt)
        blended_lag.append(lag)
    lanes["blended_pass_through"] = blended_pt
    lanes["blended_contract_lag_weeks"] = blended_lag

    # --- Structural exposure ---
    # = annual_fuel_cost * (1 - blended_pass_through)
    # The dollar amount the company would absorb at steady-state under any sustained
    # upward fuel cost move, regardless of shock magnitude.
    lanes["structural_exposure_usd"] = (
        lanes["annual_fuel_cost_usd"] * (1.0 - lanes["blended_pass_through"])
    )

    # --- Network totals ---
    total_cost = float(lanes["annual_transportation_cost_usd"].sum())
    total_fuel_cost = float(lanes["annual_fuel_cost_usd"].sum())
    total_structural = float(lanes["structural_exposure_usd"].sum())

    # Network blended pass-through: weighted by annual fuel cost (the conceptually
    # correct weight, since pass-through applies to fuel cost changes).
    network_blended_pt = float(
        (lanes["blended_pass_through"] * lanes["annual_fuel_cost_usd"]).sum()
        / lanes["annual_fuel_cost_usd"].sum()
    )

    earliest_first = int(lanes["combined_lag_weeks"].min())
    latest_first = int(lanes["combined_lag_weeks"].max())

    # --- Aggregates by mode ---
    by_mode = (
        lanes.groupby("mode", as_index=False)
        .agg(
            lane_count=("lane_id", "count"),
            annual_transportation_cost_usd=("annual_transportation_cost_usd", "sum"),
            annual_fuel_cost_usd=("annual_fuel_cost_usd", "sum"),
            structural_exposure_usd=("structural_exposure_usd", "sum"),
            annual_volume_tons=("annual_volume_tons", "sum"),
        )
    )
    by_mode["cost_share"] = by_mode["annual_transportation_cost_usd"] / total_cost
    by_mode["structural_exposure_share"] = (
        by_mode["structural_exposure_usd"] / total_structural
    )

    # --- Aggregates by sub_mode ---
    by_sub_mode = (
        lanes.groupby("sub_mode", as_index=False)
        .agg(
            mode=("mode", "first"),
            fuel_intensity_kg_per_ton_km=("fuel_intensity_kg_per_ton_km", "first"),
            lane_count=("lane_id", "count"),
            annual_transportation_cost_usd=("annual_transportation_cost_usd", "sum"),
            annual_fuel_cost_usd=("annual_fuel_cost_usd", "sum"),
            structural_exposure_usd=("structural_exposure_usd", "sum"),
            annual_volume_tons=("annual_volume_tons", "sum"),
        )
    )
    by_sub_mode["cost_share"] = (
        by_sub_mode["annual_transportation_cost_usd"] / total_cost
    )

    # --- Aggregates by lane_type ---
    by_lane_type = (
        lanes.groupby("lane_type", as_index=False)
        .agg(
            lane_count=("lane_id", "count"),
            annual_transportation_cost_usd=("annual_transportation_cost_usd", "sum"),
            annual_fuel_cost_usd=("annual_fuel_cost_usd", "sum"),
            structural_exposure_usd=("structural_exposure_usd", "sum"),
            annual_volume_tons=("annual_volume_tons", "sum"),
        )
    )
    by_lane_type["cost_share"] = (
        by_lane_type["annual_transportation_cost_usd"] / total_cost
    )
    by_lane_type["structural_exposure_share"] = (
        by_lane_type["structural_exposure_usd"] / total_structural
    )

    # --- Aggregates by archetype (volume-weighted) ---
    contracts = network.lane_contracts.copy()
    lane_volume_lookup = dict(zip(lanes["lane_id"], lanes["annual_volume_tons"]))
    contracts["weighted_volume"] = (
        contracts["lane_id"].map(lane_volume_lookup) * contracts["share_of_lane_volume"]
    )
    total_weighted_vol = float(contracts["weighted_volume"].sum())
    by_archetype = (
        contracts.groupby("contract_archetype", as_index=False)
        .agg(weighted_volume=("weighted_volume", "sum"))
    )
    by_archetype["volume_share"] = by_archetype["weighted_volume"] / total_weighted_vol
    by_archetype = by_archetype.rename(columns={"contract_archetype": "archetype"})

    # --- Vulnerability fingerprint ---
    fingerprint = _build_fingerprint(
        lanes, contracts, archetypes,
        total_weighted_vol, network_blended_pt
    )

    # Final per-lane DataFrame: keep the derived columns clean
    lane_cols = [
        "lane_id", "origin_region", "destination_region", "lane_type",
        "sub_mode", "mode", "fuel_type",
        "distance_km", "annual_volume_tons", "annual_transportation_cost_usd",
        "annual_fuel_cost_usd", "fuel_share", "fuel_cost_source",
        "fuel_intensity_kg_per_ton_km", "high_intensity_flag",
        "market_lag_weeks", "procurement_lag_weeks", "combined_lag_weeks",
        "blended_pass_through", "blended_contract_lag_weeks",
        "structural_exposure_usd",
    ]
    lane_diagnostic = lanes[lane_cols].copy()

    return NetworkDiagnostic(
        lanes=lane_diagnostic,
        total_annual_transportation_cost_usd=total_cost,
        total_annual_fuel_cost_usd=total_fuel_cost,
        total_structural_exposure_usd=total_structural,
        network_blended_pass_through=network_blended_pt,
        earliest_first_impact_week=earliest_first,
        latest_first_impact_week=latest_first,
        by_mode=by_mode,
        by_sub_mode=by_sub_mode,
        by_lane_type=by_lane_type,
        by_archetype_volume=by_archetype,
        fingerprint=fingerprint,
    )


def _build_fingerprint(
    lanes: pd.DataFrame,
    contracts: pd.DataFrame,
    archetypes: pd.DataFrame,
    total_weighted_vol: float,
    network_blended_pt: float,
) -> dict[str, str]:
    """Build the small vulnerability fingerprint for the dashboard footer."""
    fp: dict[str, str] = {}

    # Fuel-intensity weighted average (weighted by ton-km of activity)
    lanes_with_tonkm = lanes.copy()
    lanes_with_tonkm["tonkm"] = (
        lanes_with_tonkm["annual_volume_tons"] * lanes_with_tonkm["distance_km"]
    )
    weighted_intensity = float(
        (lanes_with_tonkm["fuel_intensity_kg_per_ton_km"] * lanes_with_tonkm["tonkm"]).sum()
        / lanes_with_tonkm["tonkm"].sum()
    )
    fp["fuel_intensity_weighted_avg"] = f"{weighted_intensity:.3f} kg/ton-km"

    # High-intensity volume share
    high_intensity_vol = lanes[lanes["high_intensity_flag"]]["annual_volume_tons"].sum()
    total_vol = lanes["annual_volume_tons"].sum()
    fp["high_intensity_volume_share"] = (
        f"{high_intensity_vol / total_vol:.0%} of volume on high-intensity sub-modes "
        f"(air_narrowbody, ocean_feeder, truck_shorthaul)"
    )

    # Spot exposure (% of volume on spot)
    spot_vol = float(
        contracts[contracts["contract_archetype"] == "spot"]["weighted_volume"].sum()
    )
    fp["spot_volume_share"] = (
        f"{spot_vol / total_weighted_vol:.0%} of volume on spot contracts (95% pass-through)"
    )

    # Fixed insulation
    fixed_vol = float(
        contracts[contracts["contract_archetype"] == "fixed"]["weighted_volume"].sum()
    )
    fp["fixed_volume_share"] = (
        f"{fixed_vol / total_weighted_vol:.0%} of volume on fixed contracts "
        f"(0% pass-through, fully insulated)"
    )

    # Network blended pass-through
    fp["network_blended_pass_through"] = (
        f"Network blended pass-through: {network_blended_pt:.0%} "
        f"(provider absorbs {1 - network_blended_pt:.0%} indefinitely)"
    )

    # First-impact range
    earliest = int(lanes["combined_lag_weeks"].min())
    latest = int(lanes["combined_lag_weeks"].max())
    fp["first_impact_range"] = (
        f"First impact lag: week {earliest} (truck) to week {latest} (ocean) under any sustained shock"
    )

    return fp
