import streamlit as st
import plotly.express as px

st.title("Dashboard 1: Average Inventory")

if "inventory_data" not in st.session_state or st.session_state["inventory_data"] is None:
    st.warning("Please upload data first.")
    st.stop()

df = st.session_state["inventory_data"]
# ---------------------------------------------------
# Standardize key columns as string
# ---------------------------------------------------

df["location"] = df["location"].astype(str)
df["product"] = df["product"].astype(str)


# -----------------------------
# TABLE SECTION
# -----------------------------
st.header("Table: Average Inventory")

locations_table = st.multiselect(
    "Select Location (Table)",
    df["location"].unique(),
    default=df["location"].unique(),
    key="table_loc"
)

products_table = st.multiselect(
    "Select Product (Table)",
    df["product"].unique(),
    default=df["product"].unique(),
    key="table_prod"
)

granularity_table = st.selectbox(
    "Granularity (Table)",
    ["location", "product", "year_month"],
    key="table_gran"
)

df_table = df[
    (df["location"].isin(locations_table)) &
    (df["product"].isin(products_table))
]

if df_table.empty:
    st.warning("No data after filtering (Table).")
else:
    grouped_table = df_table.groupby(granularity_table).agg(
        total_inventory=("quantity", "sum"),
        num_days=("date", "nunique")
    )

    grouped_table["average_inventory"] = (
        grouped_table["total_inventory"] / grouped_table["num_days"]
    )

    st.dataframe(grouped_table.reset_index(), use_container_width=True)


# -----------------------------
# BAR CHART SECTION
# -----------------------------
st.header("Bar Chart: Average Inventory")

locations_bar = st.multiselect(
    "Select Location (Bar)",
    df["location"].unique(),
    default=df["location"].unique(),
    key="bar_loc"
)

products_bar = st.multiselect(
    "Select Product (Bar)",
    df["product"].unique(),
    default=df["product"].unique(),
    key="bar_prod"
)

granularity_bar = st.selectbox(
    "Granularity (Bar)",
    ["location", "product", "year_month"],
    key="bar_gran"
)

sort_order = st.radio(
    "Sort Order",
    ["Descending", "Ascending"],
    horizontal=True
)

df_bar = df[
    (df["location"].isin(locations_bar)) &
    (df["product"].isin(products_bar))
]

if df_bar.empty:
    st.warning("No data after filtering (Bar).")
else:
    grouped_bar = df_bar.groupby(granularity_bar).agg(
        total_inventory=("quantity", "sum"),
        num_days=("date", "nunique")
    )

    grouped_bar["average_inventory"] = (
        grouped_bar["total_inventory"] / grouped_bar["num_days"]
    )

    grouped_bar = grouped_bar.sort_values(
        "average_inventory",
        ascending=(sort_order == "Ascending")
    )

    fig = px.bar(
        grouped_bar.reset_index(),
        x=granularity_bar,
        y="average_inventory"
    )

    st.plotly_chart(fig, use_container_width=True)
