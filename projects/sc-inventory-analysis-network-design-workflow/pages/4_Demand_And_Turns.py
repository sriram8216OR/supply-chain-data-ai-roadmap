import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Page 4: Demand Upload & Average Daily Demand")

# --------------------------------------------------
# STEP 1: Ask File Type
# --------------------------------------------------

file_option = st.radio(
    "How is demand data available?",
    [
        "Single aggregated demand file",
        "Two separate files (Customer + Interfacility)"
    ]
)

# --------------------------------------------------
# Helper Function
# --------------------------------------------------

def process_demand_file(uploaded_file, days, key_prefix):

    if uploaded_file is None:
        return None

    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file)
    else:
        df_raw = pd.read_excel(uploaded_file)

    columns = df_raw.columns.tolist()

    st.subheader(f"Map Columns - {key_prefix}")

    origin_col = st.selectbox(
        "Select Origin Location Column",
        columns,
        key=f"{key_prefix}_origin"
    )

    product_col = st.selectbox(
        "Select Product Column",
        columns,
        key=f"{key_prefix}_product"
    )

    demand_col = st.selectbox(
        "Select Demand Quantity Column",
        columns,
        key=f"{key_prefix}_demand"
    )

    df = df_raw.rename(columns={
        origin_col: "location",
        product_col: "product",
        demand_col: "demand_qty"
    })
    
    # ✅ Force business keys to string
    df["location"] = df["location"].astype(str)
    df["product"] = df["product"].astype(str)

    # ✅ Ensure numeric demand
    df["demand_qty"] = pd.to_numeric(df["demand_qty"], errors="coerce")
    df = df.dropna(subset=["demand_qty"])

    df["days"] = days

    return df[["location", "product", "demand_qty", "days"]]


# --------------------------------------------------
# STEP 2: Upload Files
# --------------------------------------------------

demand_dfs = []

if file_option == "Single aggregated demand file":

    days_1 = st.number_input(
        "How many days does this file represent?",
        min_value=1,
        value=30
    )

    file_1 = st.file_uploader(
        "Upload Demand File",
        type=["csv", "xlsx"],
        key="file1"
    )

    df1 = process_demand_file(file_1, days_1, "file1")

    if df1 is not None:
        demand_dfs.append(df1)

else:

    # Customer File
    st.subheader("Customer Demand File")

    days_customer = st.number_input(
        "Days represented (Customer File)",
        min_value=1,
        value=30,
        key="days_customer"
    )

    file_customer = st.file_uploader(
        "Upload Customer Demand File",
        type=["csv", "xlsx"],
        key="customer"
    )

    df_customer = process_demand_file(
        file_customer,
        days_customer,
        "customer"
    )

    if df_customer is not None:
        demand_dfs.append(df_customer)

    # Interfacility File
    st.subheader("Interfacility Demand File")

    days_inter = st.number_input(
        "Days represented (Interfacility File)",
        min_value=1,
        value=30,
        key="days_inter"
    )

    file_inter = st.file_uploader(
        "Upload Interfacility Demand File",
        type=["csv", "xlsx"],
        key="inter"
    )

    df_inter = process_demand_file(
        file_inter,
        days_inter,
        "inter"
    )

    if df_inter is not None:
        demand_dfs.append(df_inter)


# --------------------------------------------------
# STEP 3: Calculate Average Daily Demand
# --------------------------------------------------

if len(demand_dfs) > 0:

    combined = pd.concat(demand_dfs, ignore_index=True)

    # Aggregate demand
    grouped = combined.groupby(["location", "product"]).agg(
        total_demand=("demand_qty", "sum"),
        total_days=("days", "sum")
    )

    grouped["average_daily_demand"] = (
        grouped["total_demand"] / grouped["total_days"]
    )

    grouped = grouped.reset_index()
    st.session_state["demand_data"] = grouped


    st.success("Demand data processed successfully ✅")

    # --------------------------------------------------
    # STEP 4: Granularity Selection
    # --------------------------------------------------

    granularity = st.selectbox(
        "Select Granularity",
        [
            "Location",
            "Product",
            "Location-Product"
        ]
    )

    if granularity == "Location":
        final = grouped.groupby("location")["average_daily_demand"].sum().reset_index()
        x_col = "location"

    elif granularity == "Product":
        final = grouped.groupby("product")["average_daily_demand"].sum().reset_index()
        x_col = "product"

    else:
        final = grouped.copy()
        x_col = "location"

    # --------------------------------------------------
    # TABLE
    # --------------------------------------------------

    st.header("Average Daily Demand Table")
    st.dataframe(final, use_container_width=True)

    # --------------------------------------------------
    # BAR CHART
    # --------------------------------------------------

    st.header("Average Daily Demand Bar Chart")

    fig = px.bar(
        final,
        x=x_col,
        y="average_daily_demand",
        title="Average Daily Demand"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Upload required demand file(s) to proceed.")
