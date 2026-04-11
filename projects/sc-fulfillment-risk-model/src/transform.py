def build_master_table(orders, customers, order_items):
    df = orders.copy()

    # Merge customers (adds location)
    df = df.merge(
        customers,
        on="customer_id",
        how="left"
    )

    # Merge order items (adds seller & product info)
    df = df.merge(
        order_items,
        on="order_id",
        how="left"
    )

    return df
def build_order_level_dataset(df):
    # Keep only one row per order
    order_df = df.groupby("order_id").agg({
        "customer_state": "first",
        "delivery_days": "first",
        "delay_days": "first",
        "is_late": "first"
    }).reset_index()

    return order_df



def seller_performance_order_level(df):
    # Keep unique seller-order combinations
    seller_orders = df[["seller_id", "order_id", "is_late"]].drop_duplicates()

    seller_df = seller_orders.groupby("seller_id").agg({
        "order_id": "count",
        "is_late": "mean"
    }).reset_index()

    seller_df = seller_df.rename(columns={
        "order_id": "total_orders",
        "is_late": "late_rate"
    })

    return seller_df




def seller_region_performance(df):
    # unique seller-order combinations (avoid duplication bias)
    seller_orders = df[[
        "seller_id",
        "order_id",
        "customer_state",
        "is_late"
    ]].drop_duplicates()

    # group by seller + state
    sr_df = seller_orders.groupby(
        ["seller_id", "customer_state"]
    ).agg({
        "order_id": "count",
        "is_late": "mean"
    }).reset_index()

    sr_df = sr_df.rename(columns={
        "order_id": "total_orders",
        "is_late": "late_rate"
    })

    return sr_df

def time_performance(df):
    # order-level first (avoid duplication)
    order_df = df.groupby("order_id").agg({
        "order_month": "first",
        "order_date": "first",
        "is_late": "first"
    }).reset_index()

    # monthly performance
    monthly = order_df.groupby("order_month").agg({
        "order_id": "count",
        "is_late": "mean"
    }).reset_index()

    monthly = monthly.rename(columns={
        "order_id": "total_orders",
        "is_late": "late_rate"
    })

    return monthly

def build_summary(order_df):
    summary = {}

    # Overall metrics
    summary["total_orders"] = len(order_df)
    summary["late_rate"] = order_df["is_late"].mean() * 100
    summary["avg_delay"] = order_df["delay_days"].mean()

    return summary

def top_problem_states(order_df, n=5):
    return (
        order_df.groupby("customer_state")["is_late"]
        .mean()
        .sort_values(ascending=False)
        .head(n) * 100
    )


def top_problem_sellers(seller_df, n=5):
    filtered = seller_df[seller_df["total_orders"] > 50]

    return (
        filtered.sort_values(by="late_rate", ascending=False)
        .head(n)
    )

def build_ml_dataset(df):
    # number of items in order
    items_per_order = df.groupby("order_id")["order_id"].count()

    # number of sellers per order
    sellers_per_order = df.groupby("order_id")["seller_id"].nunique()

    seller_late_rate = df.groupby("seller_id")["is_late"].mean()
    seller_route_risk = df.groupby(["seller_id", "customer_state"])["is_late"].mean()


    # merge back
    ml_df = df.drop_duplicates("order_id").copy()
    ml_df["seller_state_route"] = (ml_df["seller_id"] + "_" + ml_df["customer_state"])


    ml_df["items_per_order"] = ml_df["order_id"].map(items_per_order)
    ml_df["sellers_per_order"] = ml_df["order_id"].map(sellers_per_order)
    ml_df["seller_risk"] = ml_df["seller_id"].map(seller_late_rate)
    ml_df["seller_route_risk"] = ml_df.set_index(["seller_id", "customer_state"]).index.map(seller_route_risk)


    # Keep only valid rows (delivered orders)
    ml_df = ml_df[ml_df["order_delivered_customer_date"].notnull()]

    # Features available at purchase time
    ml_df["order_hour"] = ml_df["order_purchase_timestamp"].dt.hour
    ml_df["order_dayofweek"] = ml_df["order_purchase_timestamp"].dt.dayofweek
    ml_df["order_month"] = ml_df["order_purchase_timestamp"].dt.month
    ml_df["is_weekend"] = ml_df["order_dayofweek"].isin([5,6]).astype(int)

    ml_df["distance_per_day"] = ml_df["distance"] / (ml_df["expected_days"] + 1)
    # Select relevant columns
    ml_df = ml_df[[
    "is_late",
    "order_hour",
    "order_dayofweek",
    "order_month",
    "is_weekend",
    "items_per_order",
    "sellers_per_order",
    "distance",
    "distance_per_day",
    "expected_days",
    #"seller_id",    
    "customer_state",
    "seller_risk",
    "seller_state_route",
    "seller_route_risk"]]


    return ml_df

import numpy as np

def prepare_geo(geo_df):
    # average lat/long per zip prefix
    geo = geo_df.groupby("geolocation_zip_code_prefix").agg({
        "geolocation_lat": "mean",
        "geolocation_lng": "mean"
    }).reset_index()

    return geo

def add_distance_feature(df, geo_df, sellers_df):
    import pandas as pd
    geo = prepare_geo(geo_df)

    df = df.copy()

    # Merge customer geo
    df = df.merge(
        geo,
        left_on="customer_zip_code_prefix",
        right_on="geolocation_zip_code_prefix",
        how="left"
    ).rename(columns={
        "geolocation_lat": "cust_lat",
        "geolocation_lng": "cust_lng"
    })

    # Merge seller geo
    sellers = sellers_df.merge(
        geo,
        left_on="seller_zip_code_prefix",
        right_on="geolocation_zip_code_prefix",
        how="left"
    )

    sellers = sellers.rename(columns={
        "geolocation_lat": "seller_lat",
        "geolocation_lng": "seller_lng"
    })

    df = df.merge(
        sellers[["seller_id", "seller_lat", "seller_lng"]],
        on="seller_id",
        how="left"
    )

    # Compute distance (simple Euclidean approx)
    df["distance"] = np.sqrt(
        (df["cust_lat"] - df["seller_lat"])**2 +
        (df["cust_lng"] - df["seller_lng"])**2
    )

    return df