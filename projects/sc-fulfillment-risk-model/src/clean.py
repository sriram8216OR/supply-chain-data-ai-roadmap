import pandas as pd

def clean_orders(df):
    df = df.copy()

    date_cols = [
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]

    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # NEW: extract time features
    df["order_month"] = df["order_purchase_timestamp"].dt.to_period("M")
    df["order_date"] = df["order_purchase_timestamp"].dt.date

    return df
def add_delivery_metrics(df):
    df = df.copy()

    # Delivery time (in days)
    df["delivery_days"] = (
        df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
    ).dt.days

    # Delay (positive = late)
    df["delay_days"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.days

    # Late flag
    df["is_late"] = df["delay_days"] > 0

    df["expected_days"] = (
    df["order_estimated_delivery_date"] -
    df["order_purchase_timestamp"]).dt.days

    return df