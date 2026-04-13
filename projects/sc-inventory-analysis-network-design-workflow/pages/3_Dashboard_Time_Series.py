import streamlit as st
import plotly.express as px

st.title("Dashboard 2: Inventory Time Series")

if "inventory_data" not in st.session_state or st.session_state["inventory_data"] is None:
    st.warning("Please upload data first.")
    st.stop()

df = st.session_state["inventory_data"]

locations = st.multiselect(
    "Select Location",
    df["location"].unique(),
    default=df["location"].unique()
)

products = st.multiselect(
    "Select Product",
    df["product"].unique(),
    default=df["product"].unique()
)

granularity = st.selectbox(
    "Time Granularity",
    ["Daily", "Monthly"]
)

df_filtered = df[
    (df["location"].isin(locations)) &
    (df["product"].isin(products))
]

if df_filtered.empty:
    st.warning("No data after filtering.")
else:

    if granularity == "Monthly":
        ts = (
            df_filtered.groupby("year_month")["quantity"]
            .mean()
            .reset_index()
        )
        x_col = "year_month"
    else:
        ts = (
            df_filtered.groupby("date")["quantity"]
            .mean()
            .reset_index()
        )
        x_col = "date"

    overall_avg = ts["quantity"].mean()

    fig = px.line(
        ts,
        x=x_col,
        y="quantity",
        markers=True
    )

    fig.add_hline(
        y=overall_avg,
        line_dash="dash",
        annotation_text="Average"
    )

    st.plotly_chart(fig, use_container_width=True)
