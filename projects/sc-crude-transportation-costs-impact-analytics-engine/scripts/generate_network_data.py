"""
Network data generator for Apex HVAC Global (synthetic HVAC manufacturer persona).

Produces:
  - data/lanes.csv         : ~80 lanes with realistic O/D, lane_type, distance, volume, cost
  - data/lane_contracts.csv: contract assignments per lane with realism rules

Design principles:
  - Apex HVAC is a manufacturer (a shipper), not a logistics company
  - Lanes hand-designed to reflect real Company Global-like supply chain
  - Lane types: inbound_component, outbound_finished, service_parts, intra_region_distribution
  - Manufacturing footprint: NAM, MEX, CHN, EU, ISC plants
  - Markets: NAM, MEX, EU, CHN domestic, MEA, LATAM, SEA, ISC domestic
  - Distances reflect real freight routes
  - Volumes scaled for ~$1.2B annual transportation spend (Company Global scale)
  - Costs derived bottom-up: physics-based fuel cost / target fuel share = total cost
  - Contracts assigned by lane_type-archetype affinity
  - Generic provider names ("Provider A" through "Provider P")
  - Fixed random seed for reproducibility

Run from project root:
    python scripts/generate_network_data.py
"""

import csv
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Reference data (mirrors the reference CSVs)
# ---------------------------------------------------------------------------

SUB_MODE_CONSUMPTION = {
    "air_widebody": 0.45,
    "air_narrowbody": 0.70,
    "ocean_ulcv": 0.010,
    "ocean_panamax": 0.018,
    "ocean_feeder": 0.030,
    "truck_longhaul": 0.025,
    "truck_shorthaul": 0.045,
}

SUB_MODE_FUEL = {
    "air_widebody": "jet",
    "air_narrowbody": "jet",
    "ocean_ulcv": "bunker",
    "ocean_panamax": "bunker",
    "ocean_feeder": "bunker",
    "truck_longhaul": "diesel",
    "truck_shorthaul": "diesel",
}

SUB_MODE_PARENT = {
    "air_widebody": "air",
    "air_narrowbody": "air",
    "ocean_ulcv": "ocean",
    "ocean_panamax": "ocean",
    "ocean_feeder": "ocean",
    "truck_longhaul": "truck",
    "truck_shorthaul": "truck",
}

# From crude_to_refined.csv - baseline prices ($/MT, April 2026 market)
FUEL_PRICE_USD_PER_MT = {
    "jet": 1672.0,
    "diesel": 1300.0,
    "bunker": 725.0,
}

# From modes.csv - expected fuel share ranges
MODE_FUEL_SHARE_RANGE = {
    "air": (0.22, 0.40),
    "ocean": (0.20, 0.50),
    "truck": (0.18, 0.40),
}

VALID_LANE_TYPES = {
    "inbound_component", "outbound_finished",
    "service_parts", "intra_region_distribution"
}

# ---------------------------------------------------------------------------
# Lane definitions (~80 lanes hand-designed for Apex HVAC realism)
#
# Each lane: (origin, destination, lane_type, sub_mode, distance_km,
#             annual_volume_tons, target_fuel_share)
# ---------------------------------------------------------------------------

LANE_DEFINITIONS = [
    # =================================================================
    # INBOUND COMPONENT FLOWS
    # Suppliers (CHN, SEA, ISC, intra-region) -> Manufacturing plants
    # =================================================================

    # CHN as global component supplier (the biggest inbound source)
    ("CHN", "NAM",   "inbound_component", "ocean_ulcv",      10400,  85000, 0.35),
    ("CHN", "MEX",   "inbound_component", "ocean_panamax",   13800,  62000, 0.35),
    ("CHN", "EU",    "inbound_component", "ocean_panamax",   20100,  48000, 0.35),
    ("CHN", "ISC",   "inbound_component", "ocean_panamax",    6200,  32000, 0.35),
    ("CHN", "NAM",   "inbound_component", "air_widebody",    11000,   3200, 0.31),
    ("CHN", "EU",    "inbound_component", "air_widebody",     8600,   2400, 0.31),
    ("CHN", "MEX",   "inbound_component", "air_widebody",    13200,   1800, 0.31),

    # SEA as electronics/sub-assembly supplier
    ("SEA", "NAM",   "inbound_component", "ocean_panamax",   12800,  42000, 0.35),
    ("SEA", "CHN",   "inbound_component", "ocean_panamax",    4300,  35000, 0.35),
    ("SEA", "EU",    "inbound_component", "ocean_panamax",   16500,  28000, 0.35),

    # ISC as growing component source
    ("ISC", "NAM",   "inbound_component", "ocean_panamax",   13900,  22000, 0.35),
    ("ISC", "EU",    "inbound_component", "ocean_panamax",   11200,  18000, 0.35),
    ("ISC", "MEA",   "inbound_component", "ocean_feeder",     2400,  14000, 0.35),

    # EU intra-region and to NAM (specialty components transatlantic)
    ("EU",  "NAM",   "inbound_component", "ocean_panamax",    6700,  18000, 0.35),
    ("EU",  "EU",    "inbound_component", "truck_longhaul",   1100,  35000, 0.29),
    ("EU",  "EU",    "inbound_component", "truck_longhaul",    850,  28000, 0.29),

    # MEX-NAM cross-border supplier flow
    ("MEX", "NAM",   "inbound_component", "truck_longhaul",   1900,  68000, 0.29),
    ("MEX", "NAM",   "inbound_component", "truck_shorthaul",   480,  42000, 0.29),

    # Intra-region domestic supplier flows
    ("NAM", "NAM",   "inbound_component", "truck_longhaul",   1400,  55000, 0.29),
    ("NAM", "NAM",   "inbound_component", "truck_longhaul",    980,  48000, 0.29),
    ("CHN", "CHN",   "inbound_component", "truck_longhaul",    820,  72000, 0.29),
    ("ISC", "ISC",   "inbound_component", "truck_longhaul",    760,  38000, 0.29),

    # =================================================================
    # OUTBOUND FINISHED GOODS FLOWS
    # Manufacturing plants -> Distribution centers / Markets
    # =================================================================

    # NAM plants serving global markets
    ("NAM", "LATAM", "outbound_finished", "ocean_panamax",    7800,  72000, 0.35),
    ("NAM", "EU",    "outbound_finished", "ocean_panamax",    6700,  38000, 0.35),
    ("NAM", "MEA",   "outbound_finished", "ocean_panamax",   13200,  28000, 0.35),

    # MEX plants — major export base for North America and global
    ("MEX", "NAM",   "outbound_finished", "truck_longhaul",   1750, 145000, 0.29),
    ("MEX", "NAM",   "outbound_finished", "truck_longhaul",   2400,  92000, 0.29),
    ("MEX", "LATAM", "outbound_finished", "ocean_panamax",    8600,  45000, 0.35),
    ("MEX", "EU",    "outbound_finished", "ocean_panamax",    9200,  18000, 0.35),

    # CHN plants — domestic distribution + global export
    ("CHN", "CHN",   "outbound_finished", "truck_longhaul",   1200, 165000, 0.29),
    ("CHN", "CHN",   "outbound_finished", "truck_longhaul",   1850, 105000, 0.29),
    ("CHN", "MEA",   "outbound_finished", "ocean_ulcv",       9700,  85000, 0.35),
    ("CHN", "SEA",   "outbound_finished", "ocean_panamax",    4300,  52000, 0.35),
    ("CHN", "EU",    "outbound_finished", "ocean_ulcv",      20100,  48000, 0.35),
    ("CHN", "LATAM", "outbound_finished", "ocean_panamax",   18200,  22000, 0.35),
    ("CHN", "ISC",   "outbound_finished", "ocean_feeder",     6200,  18000, 0.35),

    # EU plants — regional and adjacent markets
    ("EU",  "MEA",   "outbound_finished", "ocean_panamax",    5800,  42000, 0.35),
    ("EU",  "EU",    "outbound_finished", "truck_longhaul",   1200,  88000, 0.29),
    ("EU",  "EU",    "outbound_finished", "truck_longhaul",   1600,  72000, 0.29),
    ("EU",  "EU",    "outbound_finished", "truck_longhaul",    850,  62000, 0.29),
    ("EU",  "NAM",   "outbound_finished", "ocean_panamax",    6700,  15000, 0.35),

    # ISC plants — domestic and regional
    ("ISC", "ISC",   "outbound_finished", "truck_longhaul",   1400,  78000, 0.29),
    ("ISC", "MEA",   "outbound_finished", "ocean_feeder",     2400,  32000, 0.35),
    ("ISC", "SEA",   "outbound_finished", "ocean_feeder",     3900,  18000, 0.35),

    # Critical urgent finished goods (rare but exist)
    ("CHN", "MEA",   "outbound_finished", "air_widebody",     6400,   2200, 0.31),
    ("NAM", "LATAM", "outbound_finished", "air_widebody",     7400,   1800, 0.31),
    ("EU",  "MEA",   "outbound_finished", "air_widebody",     4900,   1500, 0.31),

    # NAM plants -> CHN (small, specialty equipment)
    ("NAM", "CHN",   "outbound_finished", "ocean_panamax",   10400,   8500, 0.35),

    # NAM domestic distribution from plants to regional DCs
    ("NAM", "NAM",   "outbound_finished", "truck_longhaul",   2800,  92000, 0.29),
    ("NAM", "NAM",   "outbound_finished", "truck_longhaul",   1600,  78000, 0.29),

    # =================================================================
    # SERVICE PARTS FLOWS
    # Central depots -> Regional service depots
    # =================================================================

    # NAM central depot
    ("NAM", "LATAM", "service_parts", "air_widebody",     7400,   1200, 0.31),
    ("NAM", "MEX",   "service_parts", "air_narrowbody",   1900,    900, 0.31),
    ("NAM", "EU",    "service_parts", "air_widebody",     6200,   1600, 0.31),

    # EU central depot
    ("EU",  "MEA",   "service_parts", "air_narrowbody",   4600,   1400, 0.31),
    ("EU",  "EU",    "service_parts", "air_narrowbody",   1100,   1800, 0.31),
    ("EU",  "ISC",   "service_parts", "air_widebody",     7200,    800, 0.31),

    # CHN central depot
    ("CHN", "SEA",   "service_parts", "air_narrowbody",   4200,   1100, 0.31),
    ("CHN", "ISC",   "service_parts", "air_narrowbody",   4800,    700, 0.31),
    ("CHN", "MEA",   "service_parts", "air_widebody",     6400,    900, 0.31),
    ("CHN", "CHN",   "service_parts", "truck_longhaul",   1400,   2800, 0.29),

    # Intra-region urgent service truck distribution
    ("NAM", "NAM",   "service_parts", "truck_longhaul",   1800,   3200, 0.29),
    ("EU",  "EU",    "service_parts", "truck_longhaul",   1400,   2400, 0.29),

    # Cross-region rare flows
    ("NAM", "CHN",   "service_parts", "air_widebody",    11000,    400, 0.31),
    ("ISC", "MEA",   "service_parts", "air_narrowbody",   2900,    600, 0.31),

    # =================================================================
    # INTRA-REGION DISTRIBUTION
    # Within-region last-mile from regional DCs to local markets
    # =================================================================

    # NAM intra-region distribution (densest market network)
    ("NAM", "NAM",   "intra_region_distribution", "truck_shorthaul",  280,  72000, 0.29),
    ("NAM", "NAM",   "intra_region_distribution", "truck_shorthaul",  340,  68000, 0.29),
    ("NAM", "NAM",   "intra_region_distribution", "truck_shorthaul",  220,  58000, 0.29),
    ("NAM", "NAM",   "intra_region_distribution", "truck_longhaul",   720,  82000, 0.29),
    ("NAM", "NAM",   "intra_region_distribution", "truck_longhaul",   950,  65000, 0.29),

    # EU intra-region distribution
    ("EU",  "EU",    "intra_region_distribution", "truck_shorthaul",  240,  52000, 0.29),
    ("EU",  "EU",    "intra_region_distribution", "truck_shorthaul",  290,  45000, 0.29),
    ("EU",  "EU",    "intra_region_distribution", "truck_longhaul",   620,  48000, 0.29),
    ("EU",  "EU",    "intra_region_distribution", "truck_longhaul",   780,  42000, 0.29),

    # CHN intra-region distribution
    ("CHN", "CHN",   "intra_region_distribution", "truck_shorthaul",  320,  88000, 0.29),
    ("CHN", "CHN",   "intra_region_distribution", "truck_longhaul",   650,  72000, 0.29),

    # MEA intra-region (GCC)
    ("MEA", "MEA",   "intra_region_distribution", "truck_longhaul",  1300,  32000, 0.29),
    ("MEA", "MEA",   "intra_region_distribution", "truck_shorthaul",  280,  18000, 0.29),

    # ISC intra-region (India domestic)
    ("ISC", "ISC",   "intra_region_distribution", "truck_longhaul",   980,  48000, 0.29),
    ("ISC", "ISC",   "intra_region_distribution", "truck_shorthaul",  220,  28000, 0.29),

    # LATAM intra-region (Brazil internal)
    ("LATAM", "LATAM", "intra_region_distribution", "truck_longhaul", 1200,  32000, 0.29),
]


# ---------------------------------------------------------------------------
# Compute lane economics
# ---------------------------------------------------------------------------

def compute_lane_economics(distance_km: float, volume_tons: float,
                           sub_mode: str, target_fuel_share: float):
    """Compute physics-based fuel cost and back into total transportation cost."""
    consumption = SUB_MODE_CONSUMPTION[sub_mode]
    fuel_type = SUB_MODE_FUEL[sub_mode]
    fuel_price = FUEL_PRICE_USD_PER_MT[fuel_type]

    fuel_mt = volume_tons * distance_km * consumption / 1000.0
    fuel_cost_usd = fuel_mt * fuel_price
    transportation_cost_usd = fuel_cost_usd / target_fuel_share
    actual_fuel_share = fuel_cost_usd / transportation_cost_usd

    return fuel_cost_usd, transportation_cost_usd, actual_fuel_share


# ---------------------------------------------------------------------------
# Generate lanes
# ---------------------------------------------------------------------------

def build_lanes() -> list[dict]:
    """Build the lanes with realistic economics."""
    lanes = []
    for idx, lane_def in enumerate(LANE_DEFINITIONS, start=1):
        origin, dest, lane_type, sub_mode, distance_km, volume_tons, target_share = lane_def

        mode = SUB_MODE_PARENT[sub_mode]
        share_min, share_max = MODE_FUEL_SHARE_RANGE[mode]
        jittered_share = max(share_min + 0.005,
                             min(share_max - 0.005,
                                 target_share + random.uniform(-0.02, 0.02)))

        fuel_cost, total_cost, actual_share = compute_lane_economics(
            distance_km, volume_tons, sub_mode, jittered_share
        )

        lanes.append({
            "lane_id": f"L{idx:03d}",
            "origin_region": origin,
            "destination_region": dest,
            "lane_type": lane_type,
            "sub_mode": sub_mode,
            "distance_km": round(distance_km, 1),
            "annual_volume_tons": round(volume_tons, 1),
            "annual_transportation_cost_usd": round(total_cost, 0),
            "_mode": mode,
            "_fuel_cost": fuel_cost,
            "_fuel_share": actual_share,
        })

    return lanes


# ---------------------------------------------------------------------------
# Generate lane contracts
# ---------------------------------------------------------------------------

PROVIDERS = [f"Provider {chr(ord('A') + i)}" for i in range(16)]

ARCHETYPE_WEIGHTS_BY_LANE_TYPE = {
    "inbound_component": {
        "spot": 0.05,
        "indexed_short": 0.10,
        "indexed_medium": 0.40,
        "baf_long": 0.35,
        "fixed": 0.10,
    },
    "outbound_finished": {
        "spot": 0.10,
        "indexed_short": 0.10,
        "indexed_medium": 0.35,
        "baf_long": 0.30,
        "fixed": 0.15,
    },
    "service_parts": {
        "spot": 0.45,
        "indexed_short": 0.35,
        "indexed_medium": 0.15,
        "baf_long": 0.03,
        "fixed": 0.02,
    },
    "intra_region_distribution": {
        "spot": 0.20,
        "indexed_short": 0.50,
        "indexed_medium": 0.15,
        "baf_long": 0.05,
        "fixed": 0.10,
    },
}


def assign_volume_tier(lane: dict, all_lanes: list[dict]) -> str:
    """Categorize a lane as high/mid/low volume by quartile within its mode."""
    same_mode = [l for l in all_lanes if l["_mode"] == lane["_mode"]]
    sorted_volumes = sorted([l["annual_volume_tons"] for l in same_mode], reverse=True)
    n = len(sorted_volumes)
    top_25 = sorted_volumes[max(0, n // 4 - 1)]
    bot_25 = sorted_volumes[3 * n // 4]
    v = lane["annual_volume_tons"]
    if v >= top_25:
        return "high"
    elif v >= bot_25:
        return "mid"
    else:
        return "low"


def num_contracts_for_lane(volume_tier: str, lane_type: str) -> int:
    """Number of contracts (providers) on a lane."""
    if lane_type == "service_parts":
        return random.choices([1, 2], weights=[0.65, 0.35])[0]

    if volume_tier == "high":
        return random.choices([2, 3, 4], weights=[0.45, 0.40, 0.15])[0]
    elif volume_tier == "mid":
        return random.choices([1, 2, 3], weights=[0.30, 0.50, 0.20])[0]
    else:
        return random.choices([1, 2], weights=[0.55, 0.45])[0]


def pick_archetype_for_share(lane_type: str, volume_tier: str, is_primary: bool,
                             already_used: set) -> str:
    """Pick a contract archetype for one share of a lane."""
    weights = dict(ARCHETYPE_WEIGHTS_BY_LANE_TYPE[lane_type])

    if volume_tier == "high" and is_primary and lane_type != "service_parts":
        spot_weight = weights.pop("spot", 0)
        remaining_total = sum(weights.values())
        if remaining_total > 0:
            for k in weights:
                weights[k] += spot_weight * (weights[k] / remaining_total)
        weights["spot"] = 0.0

    available = {k: v for k, v in weights.items() if k not in already_used and v > 0}
    if not available:
        available = {k: v for k, v in weights.items() if v > 0}

    archetypes = list(available.keys())
    weights_list = list(available.values())
    return random.choices(archetypes, weights=weights_list)[0]


def generate_share_splits(n_contracts: int) -> list[float]:
    """Generate realistic share splits summing to 1.0."""
    base_patterns = {
        1: [1.0],
        2: [0.65, 0.35],
        3: [0.55, 0.30, 0.15],
        4: [0.45, 0.25, 0.20, 0.10],
    }
    base = base_patterns[n_contracts]
    if n_contracts == 1:
        return [1.0]

    jittered = []
    for s in base[:-1]:
        jittered.append(round(s + random.uniform(-0.05, 0.05), 3))
    last = round(1.0 - sum(jittered), 3)

    if last < 0.05:
        deficit = 0.05 - last
        max_idx = jittered.index(max(jittered))
        jittered[max_idx] = round(jittered[max_idx] - deficit, 3)
        last = 0.05

    shares = jittered + [last]
    diff = round(1.0 - sum(shares), 6)
    if abs(diff) > 1e-9:
        max_idx = shares.index(max(shares))
        shares[max_idx] = round(shares[max_idx] + diff, 6)

    return shares


def build_lane_contracts(lanes: list[dict]) -> list[dict]:
    """Build the lane_contracts.csv data."""
    rows = []
    for lane in lanes:
        lane_type = lane["lane_type"]
        volume_tier = assign_volume_tier(lane, lanes)
        n_contracts = num_contracts_for_lane(volume_tier, lane_type)
        shares = generate_share_splits(n_contracts)

        providers_for_lane = random.sample(PROVIDERS, n_contracts)
        archetypes_used = set()
        archetypes_for_lane = []
        for i in range(n_contracts):
            archetype = pick_archetype_for_share(
                lane_type, volume_tier,
                is_primary=(i == 0),
                already_used=archetypes_used,
            )
            archetypes_used.add(archetype)
            archetypes_for_lane.append(archetype)

        for provider, archetype, share in zip(providers_for_lane, archetypes_for_lane, shares):
            rows.append({
                "lane_id": lane["lane_id"],
                "provider_name": provider,
                "contract_archetype": archetype,
                "share_of_lane_volume": share,
            })

    return rows


# ---------------------------------------------------------------------------
# Self-validation
# ---------------------------------------------------------------------------

def self_validate(lanes: list[dict], contracts: list[dict],
                  region_codes: set) -> list[str]:
    """Run full validation per the methodology."""
    issues = []

    lane_ids = [l["lane_id"] for l in lanes]
    if len(lane_ids) != len(set(lane_ids)):
        issues.append("Duplicate lane_id detected")

    for lane in lanes:
        if lane["lane_type"] not in VALID_LANE_TYPES:
            issues.append(f"Lane {lane['lane_id']}: invalid lane_type {lane['lane_type']}")

    for lane in lanes:
        if lane["origin_region"] not in region_codes:
            issues.append(f"Lane {lane['lane_id']}: origin_region {lane['origin_region']} not in region_anchors")
        if lane["destination_region"] not in region_codes:
            issues.append(f"Lane {lane['lane_id']}: destination_region {lane['destination_region']} not in region_anchors")

    for lane in lanes:
        same_region = lane["origin_region"] == lane["destination_region"]
        lt = lane["lane_type"]
        if lt == "intra_region_distribution" and not same_region:
            issues.append(f"Lane {lane['lane_id']}: intra_region_distribution must have origin == destination")
        # Other lane types allow either same-region or cross-region per methodology.

    for lane in lanes:
        if lane["distance_km"] <= 0 or lane["distance_km"] >= 30000:
            issues.append(f"Lane {lane['lane_id']}: distance {lane['distance_km']} out of bounds")
        if lane["annual_volume_tons"] <= 0:
            issues.append(f"Lane {lane['lane_id']}: non-positive volume")
        if lane["annual_transportation_cost_usd"] <= 0:
            issues.append(f"Lane {lane['lane_id']}: non-positive cost")

    for lane in lanes:
        share_min, share_max = MODE_FUEL_SHARE_RANGE[lane["_mode"]]
        if not (share_min - 0.07 <= lane["_fuel_share"] <= share_max + 0.07):
            issues.append(
                f"Lane {lane['lane_id']}: fuel share {lane['_fuel_share']:.3f} "
                f"outside band [{share_min}, {share_max}] by >7pp"
            )

    contracted_lanes = set(c["lane_id"] for c in contracts)
    for lane in lanes:
        if lane["lane_id"] not in contracted_lanes:
            issues.append(f"Lane {lane['lane_id']}: no contracts assigned")

    from collections import defaultdict
    share_sums = defaultdict(float)
    for c in contracts:
        share_sums[c["lane_id"]] += c["share_of_lane_volume"]
    for lane_id, total in share_sums.items():
        if abs(total - 1.0) > 0.001:
            issues.append(f"Lane {lane_id}: share sum {total:.4f} != 1.0")

    contract_counts = defaultdict(int)
    for c in contracts:
        contract_counts[c["lane_id"]] += 1
    for lane_id, count in contract_counts.items():
        if count < 1 or count > 5:
            issues.append(f"Lane {lane_id}: {count} contracts (must be 1-5)")

    seen = set()
    for c in contracts:
        key = (c["lane_id"], c["provider_name"])
        if key in seen:
            issues.append(f"Duplicate (lane, provider): {key}")
        seen.add(key)

    return issues


def soft_validate(lanes: list[dict], contracts: list[dict]) -> list[str]:
    """Soft sanity checks."""
    warnings = []

    total_cost = sum(l["annual_transportation_cost_usd"] for l in lanes)
    if total_cost < 300_000_000 or total_cost > 3_000_000_000:
        warnings.append(
            f"Total network cost ${total_cost:,.0f} outside plausible HVAC manufacturer range "
            f"$300M - $3B"
        )

    from collections import Counter
    archetype_counts = Counter(c["contract_archetype"] for c in contracts)
    total_contracts = len(contracts)
    for arch, count in archetype_counts.items():
        pct = count / total_contracts
        if pct < 0.01 or pct > 0.70:
            warnings.append(
                f"Archetype '{arch}' is {pct:.1%} of contracts (outside 1%-70% band)"
            )

    return warnings


def read_region_codes(data_dir: Path) -> set:
    """Read region_anchors.csv and return the set of valid region codes."""
    region_path = data_dir / "region_anchors.csv"
    if not region_path.exists():
        raise FileNotFoundError(f"region_anchors.csv not found at {region_path}")
    codes = set()
    with open(region_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            codes.add(row["region_code"])
    return codes


def write_lanes_csv(lanes: list[dict], path: Path):
    fieldnames = ["lane_id", "origin_region", "destination_region", "lane_type",
                  "sub_mode", "distance_km", "annual_volume_tons",
                  "annual_transportation_cost_usd"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lane in lanes:
            row = {k: lane[k] for k in fieldnames}
            writer.writerow(row)


def write_lane_contracts_csv(contracts: list[dict], path: Path):
    fieldnames = ["lane_id", "provider_name", "contract_archetype", "share_of_lane_volume"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in contracts:
            writer.writerow(row)


def main():
    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(exist_ok=True)

    print("Reading region anchors...")
    region_codes = read_region_codes(out_dir)
    print(f"  {len(region_codes)} regions: {sorted(region_codes)}")

    print("Building lanes...")
    lanes = build_lanes()
    print(f"  {len(lanes)} lanes generated")

    print("Building lane contracts...")
    contracts = build_lane_contracts(lanes)
    print(f"  {len(contracts)} lane-contract rows generated")

    print("\nValidating (hard checks)...")
    hard_issues = self_validate(lanes, contracts, region_codes)
    if hard_issues:
        print(f"  FAILED with {len(hard_issues)} issues:")
        for issue in hard_issues:
            print(f"    - {issue}")
        raise SystemExit(1)
    print("  All hard checks passed.")

    print("\nValidating (soft sanity checks)...")
    warnings = soft_validate(lanes, contracts)
    if warnings:
        print(f"  {len(warnings)} warnings:")
        for w in warnings:
            print(f"    - {w}")
    else:
        print("  All soft checks passed.")

    write_lanes_csv(lanes, out_dir / "lanes.csv")
    write_lane_contracts_csv(contracts, out_dir / "lane_contracts.csv")
    print(f"\nWrote {out_dir / 'lanes.csv'}")
    print(f"Wrote {out_dir / 'lane_contracts.csv'}")

    total_cost = sum(l["annual_transportation_cost_usd"] for l in lanes)
    total_volume = sum(l["annual_volume_tons"] for l in lanes)

    by_mode = {}
    for l in lanes:
        m = l["_mode"]
        by_mode.setdefault(m, {"count": 0, "cost": 0, "volume": 0})
        by_mode[m]["count"] += 1
        by_mode[m]["cost"] += l["annual_transportation_cost_usd"]
        by_mode[m]["volume"] += l["annual_volume_tons"]

    by_lane_type = {}
    for l in lanes:
        lt = l["lane_type"]
        by_lane_type.setdefault(lt, {"count": 0, "cost": 0, "volume": 0})
        by_lane_type[lt]["count"] += 1
        by_lane_type[lt]["cost"] += l["annual_transportation_cost_usd"]
        by_lane_type[lt]["volume"] += l["annual_volume_tons"]

    print("\n=== Network Summary ===")
    print(f"Total lanes: {len(lanes)}")
    print(f"Total annual transportation cost: ${total_cost:,.0f}")
    print(f"Total annual volume: {total_volume:,.0f} tons")
    print(f"Total contract rows: {len(contracts)}\n")

    print("=== By Mode ===")
    print(f"{'Mode':<10}{'Lanes':<10}{'Cost ($)':<22}{'Volume (t)':<18}{'Cost share':<12}")
    for mode in ["air", "ocean", "truck"]:
        d = by_mode[mode]
        cost_share = d["cost"] / total_cost
        print(f"{mode:<10}{d['count']:<10}${d['cost']:>16,.0f}    {d['volume']:>14,.0f}    {cost_share:>10.1%}")

    print("\n=== By Lane Type ===")
    print(f"{'Lane Type':<32}{'Lanes':<10}{'Cost ($)':<22}{'Cost share':<12}")
    for lt in ["inbound_component", "outbound_finished", "service_parts", "intra_region_distribution"]:
        d = by_lane_type.get(lt, {"count": 0, "cost": 0, "volume": 0})
        cost_share = d["cost"] / total_cost if total_cost > 0 else 0
        print(f"{lt:<32}{d['count']:<10}${d['cost']:>16,.0f}    {cost_share:>10.1%}")


if __name__ == "__main__":
    main()
