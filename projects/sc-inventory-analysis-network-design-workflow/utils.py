import streamlit as st

def apply_filters(df, key_prefix):

    st.subheader("Filters")

    locations = st.multiselect(
        "Select Location",
        df["location"].unique(),
        default=df["location"].unique(),
        key=f"{key_prefix}_location"
    )

    products = st.multiselect(
        "Select Product",
        df["product"].unique(),
        default=df["product"].unique(),
        key=f"{key_prefix}_product"
    )

    date_range = st.date_input(
        "Select Date Range",
        [df["date"].min(), df["date"].max()],
        key=f"{key_prefix}_date"
    )

    filtered = df[
        (df["location"].isin(locations)) &
        (df["product"].isin(products)) &
        (df["date"] >= pd.to_datetime(date_range[0])) &
        (df["date"] <= pd.to_datetime(date_range[1]))
    ]

    return filtered
