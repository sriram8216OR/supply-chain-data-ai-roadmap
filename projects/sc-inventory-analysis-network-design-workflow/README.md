# 📦 AI-Powered Inventory Dashboard

An interactive **Streamlit-based inventory analytics application** that enables users to upload inventory and demand data, analyze key performance metrics across multiple granularities, and generate actionable insights using built-in analytics and an AI chatbot assistant.

---

## 🚀 Features

### 1️⃣ Inventory Upload & Column Mapping
- Upload **CSV or Excel** inventory files
- Map key columns dynamically:
  - Location
  - Product
  - Date
  - Quantity
- Supports flexible file structures

### 2️⃣ Average Inventory Analysis
Calculate average inventory at multiple granularities:

- Location–Product
- Location
- Product
- Monthly
- Location–Product Monthly
- Location Monthly
- Product Monthly

**Formula:**
Average Inventory = Total Inventory / Number of Distinct Dates


---

### 3️⃣ Demand Analysis
- Upload CSV/Excel demand files
- Map demand columns dynamically
- Specify number of demand days (e.g., 365)
- Interactive bar charts at:
  - Location level
  - Product level
  - Location–Product level

---

### 4️⃣ Inventory Performance Metrics

#### ✅ Days of Supply (DOS)
DOS = Average Inventory / (Total Demand / Days of Demand)



#### ✅ Inventory Turns
Inventory Turns = Total Demand / Average Inventory



Dynamic tables update based on selected granularity.

---

### 5️⃣ ABC Segmentation

Classifies products into:
- **A Class** – High impact items
- **B Class** – Medium impact items
- **C Class** – Low impact items

Segmentation is based on configurable cumulative demand or consumption value thresholds.

---

### 6️⃣ AI Chatbot Utility

Built-in AI assistant that allows users to:
- Ask questions in natural language  
  - _“Which products have low DOS?”_
  - _“Show top A-class products by demand.”_
- Generate automated insights
- Get metric explanations
- Identify trends and anomalies

Enables faster and smarter decision-making.

---

## 🛠 Tech Stack

- **Python**
- **Streamlit**
- **Pandas**
- **Plotly**
- **OpenPyXL**

---

## 📂 Project Structure


inventory_dashboard/ │ ├── app.py ├── utils.py ├── pages/ │ ├── 1_Inventory_Upload.py │ ├── 2_Average_Inventory.py │ ├── 3_Demand_Analysis.py │ ├── 4_Inventory_Metrics.py │ └── requirements.txt
---
## ⚙️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/inventory-dashboard.git
cd inventory-dashboard
```text

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```text

Activate:

**Windows**
```bash
venv\Scripts\activate
```text

**Mac/Linux**
```bash
source venv/bin/activate
```text

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```text

If `requirements.txt` is missing:

```bash
pip install streamlit pandas openpyxl plotly
```text

---

## ▶️ Run the Application

```bash
streamlit run app.py
```text

The app will open in your browser at: 
http://localhost:8501



---

## 📊 Use Cases

- Supply chain performance monitoring
- Inventory optimization analysis
- Working capital improvement
- Demand-driven planning insights
- SKU prioritization using ABC segmentation

---

## ✅ Future Enhancements

- Forecasting integration
- Safety stock optimization
- Automated anomaly detection
- Role-based dashboards
- Cloud deployment (Streamlit Cloud / Azure / AWS)

---

## 📜 License

This project is open-source and available under the MIT License.

---

## 👤 Author

Developed as a scalable inventory analytics solution using Streamlit and AI-powered insights.

