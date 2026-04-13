import streamlit as st
from data_loader import load_file, map_and_standardize_columns

st.title("Step 1: Upload and Map Data")

if "inventory_data" not in st.session_state:
    st.session_state["inventory_data"] = None

uploaded_file = st.file_uploader(
    "Upload Inventory File (CSV or Excel)",
    type=["csv", "xlsx"]
)

if uploaded_file:

    df_raw = load_file(uploaded_file)
    columns = df_raw.columns.tolist()

    date_col = st.selectbox("Select Date Column", columns)
    location_col = st.selectbox("Select Location Column", columns)
    product_col = st.selectbox("Select Product Column", columns)
    quantity_col = st.selectbox("Select Quantity Column", columns)

    if st.button("Confirm Mapping"):

        if len({date_col, location_col, product_col, quantity_col}) < 4:
            st.error("Columns must be different.")
            st.stop()

        df = map_and_standardize_columns(
            df_raw,
            date_col,
            location_col,
            product_col,
            quantity_col
        )

        st.session_state["inventory_data"] = df

        st.success("✅ Data successfully loaded.")
        st.write("Data shape:", df.shape)
