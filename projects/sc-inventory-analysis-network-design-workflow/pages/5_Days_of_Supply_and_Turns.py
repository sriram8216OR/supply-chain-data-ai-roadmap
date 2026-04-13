import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Page 5: Days of Supply & Inventory Turns")

# ---------------------------------------------------
# VALIDATION
# ---------------------------------------------------

if "inventory_data" not in st.session_state:
    st.warning("Upload inventory data first.")
    st.stop()

if "demand_data" not in st.session_state:
    st.warning("Upload and process demand data first (Page 4).")
    st.stop()

inventory_df = st.session_state["inventory_data"]
demand_df = st.session_state["demand_data"]

# ---------------------------------------------------
# STEP 1: Calculate Average Inventory (Location-Product)
# ---------------------------------------------------

inventory_grouped = inventory_df.groupby(
    ["location", "product"]
).agg(
    total_inventory=("quantity", "sum"),
    num_days=("date", "nunique")
)

inventory_grouped["avg_inventory"] = (
    inventory_grouped["total_inventory"] /
    inventory_grouped["num_days"]
)

inventory_grouped = inventory_grouped.reset_index()

# ---------------------------------------------------
# STEP 2: Join Demand (Exclude missing demand)
# ---------------------------------------------------

merged = pd.merge(
    inventory_grouped,
    demand_df,
    on=["location", "product"],
    how="inner"   # Critical: excludes inventory with no demand
)

# Remove zero demand rows to avoid infinite DOS
merged = merged[merged["average_daily_demand"] > 0]

if merged.empty:
    st.warning("No matching inventory and demand combinations found.")
    st.stop()

# ---------------------------------------------------
# STEP 3: Base Calculations (Location-Product Level)
# ---------------------------------------------------

merged["days_of_supply"] = (
    merged["avg_inventory"] /
    merged["average_daily_demand"]
)

merged["inventory_turns"] = 365 / merged["days_of_supply"]

# ---------------------------------------------------
# FILTERS
# ---------------------------------------------------

st.sidebar.header("Filters")

locations = st.sidebar.multiselect(
    "Select Location",
    merged["location"].unique(),
    default=merged["location"].unique()
)

products = st.sidebar.multiselect(
    "Select Product",
    merged["product"].unique(),
    default=merged["product"].unique()
)

filtered = merged[
    (merged["location"].isin(locations)) &
    (merged["product"].isin(products))
]

if filtered.empty:
    st.warning("No data after filtering.")
    st.stop()

# ---------------------------------------------------
# GRANULARITY & MEASURE SELECTION
# ---------------------------------------------------

granularity = st.selectbox(
    "Select Granularity",
    ["Location-Product", "Location", "Product"]
)

measure = st.radio(
    "Select Measure",
    ["Days of Supply", "Inventory Turns"],
    horizontal=True
)

# ---------------------------------------------------
# AGGREGATION LOGIC
# ---------------------------------------------------

if granularity == "Location-Product":
    result = filtered.copy()

elif granularity == "Location":

    agg = filtered.groupby("location").agg(
        total_inventory=("avg_inventory", "sum"),
        total_demand=("average_daily_demand", "sum")
    ).reset_index()

    agg["days_of_supply"] = agg["total_inventory"] / agg["total_demand"]
    agg["inventory_turns"] = 365 / agg["days_of_supply"]

    result = agg

else:  # Product

    agg = filtered.groupby("product").agg(
        total_inventory=("avg_inventory", "sum"),
        total_demand=("average_daily_demand", "sum")
    ).reset_index()

    agg["days_of_supply"] = agg["total_inventory"] / agg["total_demand"]
    agg["inventory_turns"] = 365 / agg["days_of_supply"]

    result = agg

# ---------------------------------------------------
# TABLE DISPLAY
# ---------------------------------------------------

st.header("Results Table")

if measure == "Days of Supply":
    display_col = "days_of_supply"
else:
    display_col = "inventory_turns"

st.dataframe(result, use_container_width=True)

# ---------------------------------------------------
# BAR CHART
# ---------------------------------------------------

st.header("Bar Chart")

if granularity == "Location-Product":
    x_col = "location"
elif granularity == "Location":
    x_col = "location"
else:
    x_col = "product"

fig = px.bar(
    result,
    x=x_col,
    y=display_col,
    title=measure
)

st.plotly_chart(fig, use_container_width=True)
