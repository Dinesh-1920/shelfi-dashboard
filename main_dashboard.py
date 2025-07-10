# 📁 File: main_dashboard.py
import streamlit as st
import pandas as pd
import time
import requests
from handlers.product_config import load_product_controls
from handlers.model_logic import predict_weight, partial_train_model
from handlers.quantity_logic import detect_action, update_quantity_tracker

FIREBASE_LIVE_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data.json"

# ────── Session State Setup ──────
for k, v in {
    "products": [],
    "data": pd.DataFrame(columns=["Time", "Weight (kg)", "Predicted", "Actual", "Correct", "Action"]),
    "running": False,
    "model": None,
    "trained_rows": set(),
    "last_weight": None,
    "initial_weight": None,
    "dashboard_ready": False,
    "qty_tracker": {},
}.items():
    st.session_state.setdefault(k, v)

st.set_page_config(page_title="SHELFi Dashboard", layout="wide")
st.title("SHELFi – Modular Dashboard")

# ────── Product Config ──────
load_product_controls()

# ────── Initialize Dashboard ──────
if st.sidebar.button("🎮 Create dashboard", disabled=not st.session_state.products):
    st.session_state.qty_tracker = {p["name"]: p["quantity"] for p in st.session_state.products}
    st.session_state.initial_weight = None
    st.session_state.dashboard_ready = True
    st.success("✅ Dashboard initialized")

if not st.session_state.dashboard_ready:
    st.stop()

# ────── Controls ──────
col1, col2 = st.columns(2)
if col1.button("▶️ Start", disabled=st.session_state.running):
    st.session_state.running = True

if col2.button("⏹ Stop", disabled=not st.session_state.running):
    st.session_state.running = False

metric_ph = st.empty()
table_ph = st.empty()
qty_ph = st.empty()

# ────── Live Data Fetching ──────
if st.session_state.running:
    try:
        res = requests.get(FIREBASE_LIVE_URL)
        if res.status_code == 200:
            pkt = res.json()
            current_weight = pkt.get("weight")
            ts = time.strftime("%H:%M:%S")

            if current_weight is not None:
                if st.session_state.initial_weight is None:
                    st.session_state.initial_weight = current_weight
                    st.session_state.last_weight = current_weight
                
                delta = current_weight - st.session_state.last_weight
                st.session_state.last_weight = current_weight

                action = detect_action(delta)
                pred = "NPT" if action == "NPT" else predict_weight(current_weight)

                st.session_state.data = pd.concat([
                    st.session_state.data,
                    pd.DataFrame([{
                        "Time": ts,
                        "Weight (kg)": current_weight,
                        "Predicted": pred,
                        "Actual": "",
                        "Correct": "",
                        "Action": action
                    }])
                ], ignore_index=True)
    except Exception as e:
        st.error(f"❌ Firebase fetch error: {type(e).__name__}: {e}")

# ────── Metrics ──────
df = st.session_state.data.copy()
if not df.empty:
    mask = df["Actual"] != ""
    df.loc[mask, "Correct"] = (df["Actual"] == df["Predicted"]).map({True: "✔", False: "❌"})
    acc = (df["Correct"] == "✔").sum() / mask.sum() * 100 if mask.sum() else 0
    metric_ph.metric("✅ Accuracy", f"{acc:.1f}%", delta=f"{len(df)} packets")
    table_ph.dataframe(df)

    qty_df = pd.DataFrame([{"Product": k, "Qty Left": v} for k, v in st.session_state.qty_tracker.items()])
    qty_ph.dataframe(qty_df)

# ────── Manual Labeling ──────
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

# ────── Auto Refresh ──────
if st.session_state.running:
    time.sleep(1.5)
    st.rerun()
