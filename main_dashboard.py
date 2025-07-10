# 📁 File: main_dashboard.py
import streamlit as st
import pandas as pd
import time
import requests
from pathlib import Path
from itertools import product
from streamlit_autorefresh import st_autorefresh

from handlers.product_config import load_product_controls
from handlers.model_logic import partial_train_model, predict_weight_from_excel
from handlers.quantity_logic import detect_action, update_quantity_tracker

# Initialize session defaults
for k, v in {
    "products": [],
    "data": pd.DataFrame(columns=["Time", "Weight (kg)", "Predicted", "Actual", "Correct", "Action"]),
    "running": False,
    "model": None,
    "trained_rows": set(),
    "last_weight": None,
    "initial_weight": None,
    "packet_counter": 0,
    "dashboard_ready": False,
    "qty_tracker": {},
    "total_weight": 0.0,
    "last_processed_key": None,
}.items():
    st.session_state.setdefault(k, v)

st.set_page_config(page_title="SHELFi Dashboard", layout="wide")
st.title("SHELFi – Modular Dashboard")

# Step 1: Product input panel
load_product_controls()

# Step 2: Initialize dashboard and generate combinations Excel
if st.sidebar.button("🎮 Create dashboard", disabled=not st.session_state.products):
    st.session_state.qty_tracker = {p["name"]: p["quantity"] for p in st.session_state.products}
    st.session_state.total_weight = sum(p["weight"] * p["quantity"] for p in st.session_state.products)
    st.session_state.initial_weight = st.session_state.total_weight
    st.session_state.dashboard_ready = True

    # Generate combinations
    all_names = [p["name"] for p in st.session_state.products]
    all_weights = {p["name"]: p["weight"] for p in st.session_state.products}
    all_quantities = {p["name"]: p["quantity"] for p in st.session_state.products}

    max_qs = [list(range(0, all_quantities[name] + 1)) for name in all_names]
    rows = []
    for counts in product(*max_qs):
        if sum(counts) == 0:
            continue
        combo = []
        total_weight = 0
        for name, cnt in zip(all_names, counts):
            if cnt > 0:
                combo.extend([name] * cnt)
                total_weight += all_weights[name] * cnt
        rows.append({"Combination": "+".join(combo), "Total Weight": total_weight})

    df_comb = pd.DataFrame(rows)
    df_comb.to_excel("product_combinations.xlsx", index=False)
    st.success("Dashboard initialized and combinations saved to Excel")

if not st.session_state.dashboard_ready:
    st.stop()

# Step 3: Start/Stop and placeholders
col1, col2 = st.columns(2)
if col1.button("▶️ Start", disabled=st.session_state.running):
    st.session_state.running = True

if col2.button("⏹ Stop", disabled=not st.session_state.running):
    st.session_state.running = False

metric_ph = st.empty()
table_ph = st.empty()
qty_ph = st.empty()

# 🔁 Auto-refresh every 2 seconds when dashboard is running
if st.session_state.running:
    st_autorefresh(interval=2000, key="auto-refresh")

# Step 4: Firebase Live Data Fetch
FIREBASE_HISTORY_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/"
if st.session_state.running:
    try:
        res = requests.get(FIREBASE_HISTORY_URL, params={"_ts": time.time()})
        all_data = res.json()
        if all_data:
            keys = sorted(all_data.keys())
            latest_key = keys[-1]
            if st.session_state.last_processed_key != latest_key:
                st.session_state.last_processed_key = latest_key
                data = all_data[latest_key]
                current_weight = float(data["weight"])
                ts = latest_key.replace("-", ":")

                if st.session_state.initial_weight is None:
                    st.session_state.initial_weight = current_weight

                if st.session_state.last_weight is None:
                    st.session_state.last_weight = current_weight
                    delta = 0
                else:
                    delta = current_weight - st.session_state.last_weight
                    st.session_state.last_weight = current_weight

                action = detect_action(delta)
                pred = "NPT" if action == "NPT" else predict_weight_from_excel(current_weight, Path("product_combinations.xlsx"))

                st.session_state.data = pd.concat([
                    st.session_state.data,
                    pd.DataFrame([{ "Time": ts, "Weight (kg)": current_weight, "Predicted": pred, "Actual": "", "Correct": "", "Action": action }])
                ], ignore_index=True)

    except Exception as e:
        st.error(f"❌ Firebase Error: {type(e).__name__}: {e}")

# Step 5: Display updated metrics and tables
df = st.session_state.data.copy()
if not df.empty:
    mask = df["Actual"] != ""
    df.loc[mask, "Correct"] = (df["Actual"] == df["Predicted"]).map({True: "✔", False: "❌"})
    acc = (df["Correct"] == "✔").sum() / mask.sum() * 100 if mask.sum() else 0
    metric_ph.metric("✅ Accuracy", f"{acc:.1f}%", delta=f"{st.session_state.packet_counter} packets")
    table_ph.dataframe(df)

    qty_df = pd.DataFrame([{"Product": k, "Qty Left": v} for k, v in st.session_state.qty_tracker.items()])
    qty_ph.dataframe(qty_df)

# Step 6: Label section – always visible
st.markdown("### ✍️ Label Predictions")
unlabeled = df[df["Actual"] == ""]
if unlabeled.empty:
    st.success("✅ All data is labeled!")
else:
    row_opts = {
        f"{idx}: {r['Time']} | {r['Predicted']} | {r['Weight (kg)']:.3f}": idx
        for idx, r in unlabeled.tail(20).iterrows()
    }
    selected_row = st.selectbox("Select a row to label", list(row_opts.keys()), key="inline_label_row")
    selected_actual = st.text_input("Enter actual combination (e.g., A+B)", key="inline_label_prod")
    if st.button("✅ Save Label", key="inline_label_save"):
        idx = row_opts[selected_row]
        st.session_state.data.at[idx, "Actual"] = selected_actual
        st.success(f"Label saved for row {idx}")

        action = st.session_state.data.at[idx, "Action"]
        st.session_state.qty_tracker = update_quantity_tracker(
            st.session_state.qty_tracker,
            action,
            selected_actual
        )

        st.session_state.model, st.session_state.trained_rows = partial_train_model(
            st.session_state.data,
            st.session_state.model,
            st.session_state.trained_rows,
            st.session_state.products
        )
        st.info("Model updated after labeling.")
