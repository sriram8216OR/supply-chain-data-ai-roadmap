import streamlit as st
import pandas as pd
import requests
import uuid
from typing import Optional, List
from pydantic import Field
from langchain_core.language_models.llms import LLM
from langchain_experimental.agents import create_pandas_dataframe_agent

# ==========================================================
# 🔐 Custom Playground LLM Wrapper
# ==========================================================

class PlaygroundLLM(LLM):
    model_id: str = Field(...)
    app_id: str = Field(...)
    app_secret: str = Field(...)
    base_url: str = Field(default="https://api.ntth.ai/v1")

    token: Optional[str] = None

    # Authenticate and get JWT
    def authenticate(self):
        response = requests.post(
            f"{self.base_url}/auth/appLogin",
            json={
                "id": self.app_id,
                "secret": self.app_secret
            },
            timeout=30
        )
        response.raise_for_status()
        self.token = response.json()["token"]

    # LLM call required by LangChain
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:

        if not self.token:
            self.authenticate()

        payload = {
            "id": str(uuid.uuid4()),
            "modelId": self.model_id,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{self.base_url}/chat",
            headers=headers,
            json=payload,
            timeout=60
        )

        # Retry once if token expired
        if response.status_code == 403:
            self.authenticate()
            headers["Authorization"] = f"Bearer {self.token}"
            response = requests.post(
                f"{self.base_url}/chat",
                headers=headers,
                json=payload,
                timeout=60
            )

        response.raise_for_status()
        data = response.json()

        return data["messages"][-1]["content"]

    @property
    def _llm_type(self) -> str:
        return "playground_llm"


# ==========================================================
# 🎨 Streamlit UI
# ==========================================================

st.title("Enterprise AI Supply Chain Assistant")

# ----------------------------------------------------------
# Check Data Availability
# ----------------------------------------------------------

if "inventory_data" not in st.session_state:
    st.warning("Please upload inventory data.")
    st.stop()

inventory_df = st.session_state["inventory_data"].copy()

demand_df = st.session_state.get("demand_data", None)

# Standardize keys
inventory_df["location"] = inventory_df["location"].astype(str)
inventory_df["product"] = inventory_df["product"].astype(str)

if demand_df is not None:
    demand_df = demand_df.copy()
    demand_df["location"] = demand_df["location"].astype(str)
    demand_df["product"] = demand_df["product"].astype(str)

# ----------------------------------------------------------
# KPI Creation
# ----------------------------------------------------------

# Average inventory per product/location
avg_inventory = (
    inventory_df.groupby(["location", "product"])
    .agg(
        total_inventory=("quantity", "sum"),
        num_days=("date", "nunique")
    )
    .reset_index()
)

avg_inventory["average_inventory"] = (
    avg_inventory["total_inventory"] / avg_inventory["num_days"]
)

# Merge with demand if available
if demand_df is not None:

    merged_df = pd.merge(
        avg_inventory,
        demand_df,
        on=["location", "product"],
        how="inner"
    )

    # -------------------------------------------------
# Ensure expected demand columns exist
# -------------------------------------------------

if "demand_qty" not in merged_df.columns:
    # Try to detect renamed column
    possible_demand_cols = [
        col for col in merged_df.columns
        if "demand" in col.lower() and "qty" in col.lower()
    ]

    if possible_demand_cols:
        merged_df["demand_qty"] = merged_df[possible_demand_cols[0]]
    else:
        st.error("Demand quantity column not found after merge.")
        st.stop()

    if "days" not in merged_df.columns:
        possible_days_cols = [
            col for col in merged_df.columns
            if "day" in col.lower()
        ]

        if possible_days_cols:
            merged_df["days"] = merged_df[possible_days_cols[0]]
        else:
            st.error("Days column not found after merge.")
            st.stop()

    # -------------------------------------------------
    # KPI Calculations
    # -------------------------------------------------

    merged_df["daily_demand"] = (
        merged_df["demand_qty"] / merged_df["days"]
    )

    merged_df["days_of_supply"] = (
        merged_df["average_inventory"] / merged_df["daily_demand"]
    )

    merged_df["inventory_turns"] = (
        merged_df["demand_qty"] / merged_df["average_inventory"]
    )

else:
    merged_df = avg_inventory.copy()

# ----------------------------------------------------------
# Combine Data For AI Agent
# ----------------------------------------------------------

# We give agent access to all major tables
data_context = {
    "inventory_df": inventory_df,
    "avg_inventory": avg_inventory,
    "demand_df": demand_df,
    "merged_df": merged_df
}

# For agent we primarily expose merged_df if demand exists
primary_df = merged_df

# ----------------------------------------------------------
# Initialize LLM
# ----------------------------------------------------------

llm = PlaygroundLLM(
    model_id=st.secrets["PLAYGROUND_MODEL_ID"],
    app_id=st.secrets["PLAYGROUND_APP_ID"],
    app_secret=st.secrets["PLAYGROUND_APP_SECRET"],
)

# ----------------------------------------------------------
# Create Pandas Agent
# ----------------------------------------------------------

agent = create_pandas_dataframe_agent(
    llm,
    primary_df,
    verbose=False,
    allow_dangerous_code=False
)

# ----------------------------------------------------------
# Chat UI
# ----------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Ask anything about inventory, demand, KPIs, DOS, Turns..."):

    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing supply chain data..."):
            try:
                # Add system instruction
                enhanced_prompt = f"""
You are a supply chain analytics expert.

You have access to a dataframe called df containing:
- location
- product
- total_inventory
- num_days
- average_inventory
- demand_qty (if available)
- days
- daily_demand
- days_of_supply
- inventory_turns

Answer using data-driven reasoning.
If asked for ranking, compute.
If asked for comparison, compute.
If asked for KPI insights, analyze patterns.
                
User question:
{prompt}
"""

                response = agent.run(enhanced_prompt)

            except Exception as e:
                response = f"Error: {str(e)}"

            st.write(response)

    st.session_state.chat_history.append(
        {"role": "assistant", "content": response}
    )
