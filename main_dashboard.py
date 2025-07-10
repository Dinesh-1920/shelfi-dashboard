# 📁 File: main_dashboard.py
import streamlit as st
import pandas as pd
import threading, queue, time
from pathlib import Path
from itertools import product
from handlers.product_config import load_product_controls
from handlers.model_logic import partial_train_model, predict_weight
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
    "last_received_ts": "",
    "LIVE_QUEUE": queue.Queue(),
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
    st.session_state.initial_weight = None
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
        while not st.session_state.LIVE_QUEUE.empty() and updates < 3:
            pkt = st.session_state.LIVE_QUEUE.get_nowait()
            updates += 1
            current_weight = pkt["weight"]
            ts = pkt["ts"]

            # Prevent duplicate appends
            if ts == st.session_state.last_received_ts:
                continue
            st.session_state.last_received_ts = ts

            df_existing = st.session_state.data
            if not df_existing.empty:
                last_row = df_existing.iloc[-1]
                if last_row["Weight (kg)"] == current_weight and last_row["Time"] == ts:
                    continue  # Skip duplicate

            if st.session_state.initial_weight is None:
                st.session_state.initial_weight = current_weight
                st.session_state.last_weight = current_weight
                continue

            delta = current_weight - st.session_state.last_weight
            st.session_state.last_weight = current_weight

            action = detect_action(delta)
            pred = "NPT" if action == "NPT" else predict_weight(current_weight, Path("product_combinations.xlsx"))

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
        st.error(f"❌ Error in live loop: {type(e).__name__} - {e}")

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
    selected_actual = st.text_input("Enter actual combination (e.g., A+B)", key=f"inline_label_prod")
    if st.button("✅ Save Label", key=f"inline_label_save"):
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

# Step 7: Auto-refresh only when running
if st.session_state.running:
    time.sleep(1.5)
    st.rerun()
