# 📁 File: main_dashboard.py
import streamlit as st
import pandas as pd
import threading, queue, time
from pathlib import Path

from handlers.product_config import load_product_controls
from handlers.mqtt_handler import start_mqtt_listener
from handlers.model_logic import partial_train_model, predict_weight, generate_combinations_excel
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
}.items():
    st.session_state.setdefault(k, v)

st.set_page_config(page_title="SHELFi Dashboard", layout="wide")
st.title("SHELFi – Modular Dashboard")

# Step 1: Product input panel
load_product_controls()

# Step 2: Initialize dashboard
if st.sidebar.button("🎮 Create dashboard", disabled=not st.session_state.products):
    st.session_state.qty_tracker = {p["name"]: p["quantity"] for p in st.session_state.products}
    st.session_state.total_weight = sum(p["weight"] * p["quantity"] for p in st.session_state.products)
    st.session_state.initial_weight = st.session_state.total_weight
    st.session_state.dashboard_ready = True
    generate_combinations_excel(st.session_state.products)
    st.success("Dashboard initialized")

if not st.session_state.dashboard_ready:
    st.stop()

# Step 3: Start/Stop and placeholders
LIVE_QUEUE = st.session_state.get("LIVE_QUEUE") or queue.Queue()
st.session_state["LIVE_QUEUE"] = LIVE_QUEUE

if "mqtt_thread_started" not in st.session_state:
    def launch_mqtt():
        start_mqtt_listener(
            LIVE_QUEUE,
            "a1ct2m9u3qf028-ats.iot.ap-south-1.amazonaws.com",
            "outTopic",
            {
                "cert": Path("E:/Walmart/crets/device_cert.pem.crt"),
                "key": Path("E:/Walmart/crets/private_key.pem.key"),
                "root": Path("E:/Walmart/crets/AmazonRootCA1.pem"),
            },
        )
    threading.Thread(target=launch_mqtt, daemon=True).start()
    st.session_state.mqtt_thread_started = True

col1, col2 = st.columns(2)
if col1.button("▶️ Start", disabled=st.session_state.running):
    st.session_state.running = True

if col2.button("⏹ Stop", disabled=not st.session_state.running):
    st.session_state.running = False

metric_ph = st.empty()
table_ph = st.empty()
qty_ph = st.empty()

# Step 4: Live data handling
if st.session_state.running:
    try:
        updates = 0
        while not LIVE_QUEUE.empty() and updates < 3:
            pkt = LIVE_QUEUE.get_nowait()
            updates += 1
            current_weight = pkt["weight"]
            ts = pkt["ts"]

            if st.session_state.initial_weight is None:
                st.session_state.initial_weight = current_weight
                st.session_state.last_weight = current_weight
                continue

            delta = current_weight - st.session_state.last_weight
            st.session_state.last_weight = current_weight

            action = detect_action(delta)
            pred = predict_weight(current_weight)

            # Log data only, do not update quantity
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
        st.error(f"Error in loop: {e}")

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
    selected_actual = st.text_input("Actual product combination", key=f"inline_label_prod")
    if st.button("✅ Save Label", key=f"inline_label_save"):
        idx = row_opts[selected_row]
        st.session_state.data.at[idx, "Actual"] = selected_actual
        st.success(f"Label saved for row {idx}")

        # Update quantity tracker based on actual
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

# Step 7: Auto-refresh only when running
if st.session_state.running:
    time.sleep(1.5)
    try:
        st.experimental_rerun()
    except AttributeError:
        st.warning("⚠️ Auto-refresh failed. Please manually refresh the app.")

