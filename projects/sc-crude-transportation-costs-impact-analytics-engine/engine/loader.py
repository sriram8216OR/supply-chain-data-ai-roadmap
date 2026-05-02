"""
Loader module — reads the 6 CSVs, runs all methodology validation rules,
and returns a clean NetworkData object that downstream engine modules consume.

The loader is the single source of truth for data integrity. Every rule from
the methodology's "Cross-CSV Integrity Summary" is enforced here.

Hard violations raise ValidationError. Soft warnings are returned in
NetworkData.warnings and surfaced to the user via the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Constants from methodology
# ---------------------------------------------------------------------------

BASELINE_BRENT_USD_PER_BBL = 104.0  # April 2026 baseline reference

VALID_REFINED_PRODUCTS = {"jet", "diesel", "bunker"}
VALID_MODES = {"air", "ocean", "truck"}
VALID_SUB_MODES = {
    "air_widebody", "air_narrowbody",
    "ocean_ulcv", "ocean_panamax", "ocean_feeder",
    "truck_longhaul", "truck_shorthaul",
}
VALID_ARCHETYPES = {"spot", "indexed_short", "indexed_medium", "baf_long", "fixed"}
VALID_LANE_TYPES = {
    "inbound_component", "outbound_finished",
    "service_parts", "intra_region_distribution",
}
VALID_REGIONS = {"NAM", "MEX", "EU", "CHN", "ISC", "SEA", "MEA", "LATAM"}

# Fuel share validation tolerance per methodology
FUEL_SHARE_TOLERANCE_PP = 0.07


class ValidationError(Exception):
    """Raised when data integrity rules are violated."""
    pass


@dataclass
class NetworkData:
    """Validated network data — the single object passed to engine modules."""

    crude_to_refined: pd.DataFrame
    modes: pd.DataFrame
    sub_modes: pd.DataFrame
    contract_archetypes: pd.DataFrame
    region_anchors: pd.DataFrame
    lanes: pd.DataFrame
    lane_contracts: pd.DataFrame
    warnings: list[str] = field(default_factory=list)

    @property
    def n_lanes(self) -> int:
        return len(self.lanes)

    @property
    def n_contracts(self) -> int:
        return len(self.lane_contracts)

    @property
    def total_annual_transportation_cost(self) -> float:
        return float(self.lanes["annual_transportation_cost_usd"].sum())

    @property
    def total_annual_volume_tons(self) -> float:
        return float(self.lanes["annual_volume_tons"].sum())


# ---------------------------------------------------------------------------
# Per-file readers (each returns a typed DataFrame; raises on schema issues)
# ---------------------------------------------------------------------------

def _read_crude_to_refined(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"refined_product", "elasticity", "market_lag_weeks",
                "bbl_per_mt", "baseline_price_usd_per_mt"}
    _check_columns(df, expected, "crude_to_refined.csv")

    if len(df) != 3:
        raise ValidationError(f"crude_to_refined.csv must have exactly 3 rows; got {len(df)}")
    if set(df["refined_product"]) != VALID_REFINED_PRODUCTS:
        raise ValidationError(
            f"crude_to_refined.csv refined_product values must be {VALID_REFINED_PRODUCTS}; "
            f"got {set(df['refined_product'])}"
        )
    if df["refined_product"].duplicated().any():
        raise ValidationError("crude_to_refined.csv contains duplicate refined_product values")

    if not ((df["elasticity"] > 0) & (df["elasticity"] <= 1.2)).all():
        raise ValidationError("crude_to_refined.csv: elasticity must be in (0, 1.2]")
    if not ((df["market_lag_weeks"] >= 0) & (df["market_lag_weeks"] <= 12)).all():
        raise ValidationError("crude_to_refined.csv: market_lag_weeks must be in [0, 12]")
    if not (df["bbl_per_mt"] > 0).all():
        raise ValidationError("crude_to_refined.csv: bbl_per_mt must be > 0")
    if not (df["baseline_price_usd_per_mt"] > 0).all():
        raise ValidationError("crude_to_refined.csv: baseline_price_usd_per_mt must be > 0")

    return df


def _read_modes(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"mode", "procurement_lag_weeks",
                "expected_fuel_share_min", "expected_fuel_share_max"}
    _check_columns(df, expected, "modes.csv")

    if len(df) != 3:
        raise ValidationError(f"modes.csv must have exactly 3 rows; got {len(df)}")
    if set(df["mode"]) != VALID_MODES:
        raise ValidationError(f"modes.csv mode values must be {VALID_MODES}; got {set(df['mode'])}")
    if df["mode"].duplicated().any():
        raise ValidationError("modes.csv contains duplicate mode values")

    if not ((df["procurement_lag_weeks"] >= 0) & (df["procurement_lag_weeks"] <= 12)).all():
        raise ValidationError("modes.csv: procurement_lag_weeks must be in [0, 12]")
    if not (df["expected_fuel_share_min"] >= 0).all():
        raise ValidationError("modes.csv: expected_fuel_share_min must be >= 0")
    if not (df["expected_fuel_share_min"] < df["expected_fuel_share_max"]).all():
        raise ValidationError(
            "modes.csv: expected_fuel_share_min must be < expected_fuel_share_max"
        )
    if not (df["expected_fuel_share_max"] <= 0.6).all():
        raise ValidationError("modes.csv: expected_fuel_share_max must be <= 0.6")

    return df


def _read_sub_modes(path: Path, modes_df: pd.DataFrame,
                    refined_products: set) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"sub_mode", "mode", "fuel_type", "consumption_kg_per_ton_km"}
    _check_columns(df, expected, "sub_modes.csv")

    if len(df) != 7:
        raise ValidationError(f"sub_modes.csv must have exactly 7 rows; got {len(df)}")
    if set(df["sub_mode"]) != VALID_SUB_MODES:
        raise ValidationError(
            f"sub_modes.csv sub_mode values must be {VALID_SUB_MODES}; got {set(df['sub_mode'])}"
        )
    if df["sub_mode"].duplicated().any():
        raise ValidationError("sub_modes.csv contains duplicate sub_mode values")

    # Foreign key: mode -> modes.mode
    valid_modes = set(modes_df["mode"])
    invalid = set(df["mode"]) - valid_modes
    if invalid:
        raise ValidationError(f"sub_modes.csv: mode values {invalid} not in modes.csv")

    # Foreign key: fuel_type -> crude_to_refined.refined_product
    invalid_fuels = set(df["fuel_type"]) - refined_products
    if invalid_fuels:
        raise ValidationError(
            f"sub_modes.csv: fuel_type values {invalid_fuels} not in crude_to_refined.csv"
        )

    # Constraint: all sub-modes within a mode use the same fuel_type
    fuel_per_mode = df.groupby("mode")["fuel_type"].nunique()
    bad_modes = fuel_per_mode[fuel_per_mode > 1].index.tolist()
    if bad_modes:
        raise ValidationError(
            f"sub_modes.csv: modes {bad_modes} have sub-modes with different fuel_types"
        )

    if not ((df["consumption_kg_per_ton_km"] > 0) & (df["consumption_kg_per_ton_km"] < 5.0)).all():
        raise ValidationError(
            "sub_modes.csv: consumption_kg_per_ton_km must be in (0, 5.0)"
        )

    return df


def _read_contract_archetypes(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"archetype", "pass_through_pct", "contract_lag_weeks"}
    _check_columns(df, expected, "contract_archetypes.csv")

    if len(df) != 5:
        raise ValidationError(f"contract_archetypes.csv must have exactly 5 rows; got {len(df)}")
    if set(df["archetype"]) != VALID_ARCHETYPES:
        raise ValidationError(
            f"contract_archetypes.csv archetype values must be {VALID_ARCHETYPES}; "
            f"got {set(df['archetype'])}"
        )
    if df["archetype"].duplicated().any():
        raise ValidationError("contract_archetypes.csv contains duplicate archetype values")

    if not ((df["pass_through_pct"] >= 0) & (df["pass_through_pct"] <= 1)).all():
        raise ValidationError("contract_archetypes.csv: pass_through_pct must be in [0, 1]")
    if not (df["contract_lag_weeks"] >= 0).all():
        raise ValidationError("contract_archetypes.csv: contract_lag_weeks must be >= 0")

    return df


def _read_region_anchors(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"region_code", "anchor_city", "latitude", "longitude"}
    _check_columns(df, expected, "region_anchors.csv")

    if len(df) != 8:
        raise ValidationError(f"region_anchors.csv must have exactly 8 rows; got {len(df)}")
    if set(df["region_code"]) != VALID_REGIONS:
        raise ValidationError(
            f"region_anchors.csv region_code values must be {VALID_REGIONS}; "
            f"got {set(df['region_code'])}"
        )
    if df["region_code"].duplicated().any():
        raise ValidationError("region_anchors.csv contains duplicate region_code values")

    if not ((df["latitude"] >= -90) & (df["latitude"] <= 90)).all():
        raise ValidationError("region_anchors.csv: latitude must be in [-90, 90]")
    if not ((df["longitude"] >= -180) & (df["longitude"] <= 180)).all():
        raise ValidationError("region_anchors.csv: longitude must be in [-180, 180]")

    return df


def _read_lanes(path: Path, sub_modes_df: pd.DataFrame,
                region_anchors_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"lane_id", "origin_region", "destination_region", "lane_type",
                "sub_mode", "distance_km", "annual_volume_tons",
                "annual_transportation_cost_usd"}
    _check_columns(df, expected, "lanes.csv")

    if df["lane_id"].duplicated().any():
        raise ValidationError("lanes.csv contains duplicate lane_id values")

    valid_regions = set(region_anchors_df["region_code"])
    invalid_origins = set(df["origin_region"]) - valid_regions
    if invalid_origins:
        raise ValidationError(
            f"lanes.csv: origin_region values {invalid_origins} not in region_anchors.csv"
        )
    invalid_dests = set(df["destination_region"]) - valid_regions
    if invalid_dests:
        raise ValidationError(
            f"lanes.csv: destination_region values {invalid_dests} not in region_anchors.csv"
        )

    invalid_lane_types = set(df["lane_type"]) - VALID_LANE_TYPES
    if invalid_lane_types:
        raise ValidationError(
            f"lanes.csv: lane_type values {invalid_lane_types} not in {VALID_LANE_TYPES}"
        )

    # intra_region_distribution must have origin == destination
    intra = df[df["lane_type"] == "intra_region_distribution"]
    bad_intra = intra[intra["origin_region"] != intra["destination_region"]]
    if not bad_intra.empty:
        raise ValidationError(
            f"lanes.csv: intra_region_distribution lanes must have origin == destination. "
            f"Offending lane_ids: {bad_intra['lane_id'].tolist()}"
        )

    valid_sub_modes = set(sub_modes_df["sub_mode"])
    invalid_sub_modes = set(df["sub_mode"]) - valid_sub_modes
    if invalid_sub_modes:
        raise ValidationError(
            f"lanes.csv: sub_mode values {invalid_sub_modes} not in sub_modes.csv"
        )

    if not ((df["distance_km"] > 0) & (df["distance_km"] < 30000)).all():
        raise ValidationError("lanes.csv: distance_km must be in (0, 30000)")
    if not (df["annual_volume_tons"] > 0).all():
        raise ValidationError("lanes.csv: annual_volume_tons must be > 0")
    if not (df["annual_transportation_cost_usd"] > 0).all():
        raise ValidationError("lanes.csv: annual_transportation_cost_usd must be > 0")

    return df


def _read_lane_contracts(path: Path, lanes_df: pd.DataFrame,
                         archetypes_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"lane_id", "provider_name", "contract_archetype", "share_of_lane_volume"}
    _check_columns(df, expected, "lane_contracts.csv")

    valid_lane_ids = set(lanes_df["lane_id"])
    invalid_lanes = set(df["lane_id"]) - valid_lane_ids
    if invalid_lanes:
        raise ValidationError(
            f"lane_contracts.csv: lane_id values {invalid_lanes} not in lanes.csv"
        )

    valid_archetypes = set(archetypes_df["archetype"])
    invalid_archs = set(df["contract_archetype"]) - valid_archetypes
    if invalid_archs:
        raise ValidationError(
            f"lane_contracts.csv: contract_archetype values {invalid_archs} not in "
            f"contract_archetypes.csv"
        )

    if not ((df["share_of_lane_volume"] > 0) & (df["share_of_lane_volume"] <= 1)).all():
        raise ValidationError(
            "lane_contracts.csv: share_of_lane_volume must be in (0, 1]"
        )

    # Per-lane: shares sum to ~1.0
    share_sums = df.groupby("lane_id")["share_of_lane_volume"].sum()
    bad_sums = share_sums[(share_sums - 1.0).abs() > 0.001]
    if not bad_sums.empty:
        raise ValidationError(
            f"lane_contracts.csv: share_of_lane_volume must sum to 1.0 per lane. "
            f"Offending lanes: {bad_sums.to_dict()}"
        )

    # Per-lane: 1-5 contracts
    contract_counts = df.groupby("lane_id").size()
    bad_counts = contract_counts[(contract_counts < 1) | (contract_counts > 5)]
    if not bad_counts.empty:
        raise ValidationError(
            f"lane_contracts.csv: each lane must have 1-5 contracts. "
            f"Offending lanes: {bad_counts.to_dict()}"
        )

    # No orphan lanes
    contracted = set(df["lane_id"])
    orphans = valid_lane_ids - contracted
    if orphans:
        raise ValidationError(
            f"lanes.csv: lanes without any contract assignments: {orphans}"
        )

    # (lane_id, provider) unique
    if df.duplicated(subset=["lane_id", "provider_name"]).any():
        raise ValidationError(
            "lane_contracts.csv: (lane_id, provider_name) combinations must be unique"
        )

    return df


def _check_columns(df: pd.DataFrame, expected: set, filename: str):
    """Raise if required columns are missing."""
    missing = expected - set(df.columns)
    if missing:
        raise ValidationError(f"{filename}: missing required columns: {missing}")


# ---------------------------------------------------------------------------
# Soft sanity checks — emit warnings but don't fail
# ---------------------------------------------------------------------------

def _soft_checks(network: NetworkData) -> list[str]:
    """Compute fuel-share check per Layer B and other soft sanity checks.

    Returns list of warning messages.
    """
    warnings: list[str] = []
    lanes = network.lanes
    sub_modes = network.sub_modes
    modes = network.modes
    crude = network.crude_to_refined

    # Build lookups
    sub_mode_to_mode = dict(zip(sub_modes["sub_mode"], sub_modes["mode"]))
    sub_mode_to_consumption = dict(zip(sub_modes["sub_mode"],
                                       sub_modes["consumption_kg_per_ton_km"]))
    sub_mode_to_fuel = dict(zip(sub_modes["sub_mode"], sub_modes["fuel_type"]))
    fuel_to_price = dict(zip(crude["refined_product"],
                             crude["baseline_price_usd_per_mt"]))
    mode_share_min = dict(zip(modes["mode"], modes["expected_fuel_share_min"]))
    mode_share_max = dict(zip(modes["mode"], modes["expected_fuel_share_max"]))

    # Per-lane fuel share check + fuel cost source tagging
    fuel_costs = []
    fuel_shares = []
    fuel_cost_sources = []
    for _, lane in lanes.iterrows():
        sm = lane["sub_mode"]
        mode = sub_mode_to_mode[sm]
        consumption = sub_mode_to_consumption[sm]
        fuel = sub_mode_to_fuel[sm]
        price = fuel_to_price[fuel]

        fuel_mt = lane["annual_volume_tons"] * lane["distance_km"] * consumption / 1000.0
        fuel_cost = fuel_mt * price
        fuel_share = fuel_cost / lane["annual_transportation_cost_usd"]

        share_min = mode_share_min[mode]
        share_max = mode_share_max[mode]
        out_of_band = (fuel_share < share_min - FUEL_SHARE_TOLERANCE_PP or
                       fuel_share > share_max + FUEL_SHARE_TOLERANCE_PP)

        if out_of_band:
            # Apply fallback per methodology
            fallback = lane["annual_transportation_cost_usd"] * (share_min + share_max) / 2
            fuel_costs.append(fallback)
            fuel_shares.append((share_min + share_max) / 2)
            fuel_cost_sources.append("fallback_midpoint")
            warnings.append(
                f"Lane {lane['lane_id']}: computed fuel share {fuel_share:.1%} "
                f"outside expected band [{share_min:.0%}-{share_max:.0%}] for {mode} "
                f"by >{FUEL_SHARE_TOLERANCE_PP:.0%}. Applied fallback (mode midpoint)."
            )
        else:
            fuel_costs.append(fuel_cost)
            fuel_shares.append(fuel_share)
            fuel_cost_sources.append("physics_computed")

    # Annotate the lanes DataFrame in-place with the derived columns
    lanes["_annual_fuel_cost_usd"] = fuel_costs
    lanes["_fuel_share"] = fuel_shares
    lanes["_fuel_cost_source"] = fuel_cost_sources

    # Network total cost plausibility (manufacturer scale)
    total_cost = network.total_annual_transportation_cost
    if total_cost < 300_000_000 or total_cost > 3_000_000_000:
        warnings.append(
            f"Total network cost ${total_cost:,.0f} outside plausible HVAC manufacturer "
            f"range $300M - $3B."
        )

    # Archetype concentration check
    contracts = network.lane_contracts
    n_contracts = len(contracts)
    arch_share = contracts["contract_archetype"].value_counts() / n_contracts
    for arch, pct in arch_share.items():
        if pct < 0.01 or pct > 0.70:
            warnings.append(
                f"Archetype '{arch}' is {pct:.1%} of contracts (outside 1%-70% band)."
            )

    return warnings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_network(data_dir: str | Path) -> NetworkData:
    """Load all 6 CSVs, validate per methodology, return a NetworkData object.

    Parameters
    ----------
    data_dir : path to the directory containing the CSV files

    Returns
    -------
    NetworkData with validated DataFrames and any soft warnings

    Raises
    ------
    ValidationError if any hard validation rule is violated
    FileNotFoundError if any required CSV is missing
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    crude = _read_crude_to_refined(data_dir / "crude_to_refined.csv")
    modes = _read_modes(data_dir / "modes.csv")
    refined_products = set(crude["refined_product"])
    sub_modes = _read_sub_modes(data_dir / "sub_modes.csv", modes, refined_products)
    archetypes = _read_contract_archetypes(data_dir / "contract_archetypes.csv")
    region_anchors = _read_region_anchors(data_dir / "region_anchors.csv")
    lanes = _read_lanes(data_dir / "lanes.csv", sub_modes, region_anchors)
    lane_contracts = _read_lane_contracts(data_dir / "lane_contracts.csv",
                                          lanes, archetypes)

    network = NetworkData(
        crude_to_refined=crude,
        modes=modes,
        sub_modes=sub_modes,
        contract_archetypes=archetypes,
        region_anchors=region_anchors,
        lanes=lanes,
        lane_contracts=lane_contracts,
    )

    # Run soft checks (annotates lanes with _annual_fuel_cost_usd etc.)
    network.warnings = _soft_checks(network)

    return network
