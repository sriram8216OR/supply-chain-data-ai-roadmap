import pandas as pd


def load_file(uploaded_file):
    """
    Load CSV or Excel file
    """
    if uploaded_file.name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


def map_and_standardize_columns(
    df_raw,
    date_col,
    location_col,
    product_col,
    quantity_col
):
    """
    Rename columns and standardize types
    """

    df = df_raw.rename(columns={
        date_col: "date",
        location_col: "location",
        product_col: "product",
        quantity_col: "quantity"
    })

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["location"] = df["location"].astype(str)
    df["product"] = df["product"].astype(str)


    # Drop invalid rows
    df = df.dropna(subset=["date", "quantity"])

    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    return df
