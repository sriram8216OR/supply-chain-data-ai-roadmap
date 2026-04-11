import pandas as pd
from pathlib import Path

DATA_PATH = Path("data/raw")

def load_data():
    data = {}

    data["orders"] = pd.read_csv(DATA_PATH / "olist_orders_dataset.csv")
    data["order_items"] = pd.read_csv(DATA_PATH / "olist_order_items_dataset.csv")
    data["customers"] = pd.read_csv(DATA_PATH / "olist_customers_dataset.csv")
    data["geolocation"] = pd.read_csv(DATA_PATH / "olist_geolocation_dataset.csv")
    data["sellers"] = pd.read_csv(DATA_PATH / "olist_sellers_dataset.csv")

    return data