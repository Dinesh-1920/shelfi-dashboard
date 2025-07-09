# 📁 File: model_logic.py
import pandas as pd
import streamlit as st
import itertools

THRESHOLD_MARGIN = 0.10  # 100 grams margin


def predict_weight(current_weight, combination_excel_path="combinations.xlsx"):
    try:
        df = pd.read_excel(combination_excel_path)

        # Use last known weight instead of initial total
        last_weight = float(st.session_state.get("last_predicted_weight", st.session_state.initial_weight))
        delta = abs(last_weight - current_weight)

        df["Diff"] = (df["Total Weight"] - delta).abs()
        match = df[df["Diff"] <= THRESHOLD_MARGIN]

        if not match.empty:
            best_match = match.sort_values("Diff").iloc[0]
            st.session_state.last_predicted_weight = current_weight  # Update for next prediction
            return best_match["Combination"]
        else:
            return "Unknown"

    except Exception as e:
        print(f"[predict_weight error] {e}")
        return "Unknown"


def partial_train_model(df, model, trained_rows, product_list):
    return model, trained_rows  # No-op, as we're using the Excel for prediction


# 📁 File: combo_generator.py (in handlers/)
def generate_combinations_excel(products, max_items=6, path="combinations.xlsx"):
    rows = []

    product_weights = {p["name"]: p["weight"] for p in products}
    product_names = [p["name"] for p in products for _ in range(p["quantity"])]

    for r in range(1, max_items + 1):
        for combo in itertools.combinations_with_replacement(product_names, r):
            combo_sorted = "+".join(sorted(combo))
            total_weight = sum(product_weights[name] for name in combo)
            rows.append({"Combination": combo_sorted, "Total Weight": total_weight})

    df = pd.DataFrame(rows).drop_duplicates(subset=["Combination"])
    df.to_excel(path, index=False)
    print(f"✅ Generated combination sheet with {len(df)} rows → {path}")


# 📁 Integration in main_dashboard.py
# After the line where the dashboard is initialized (inside 'Create dashboard' button)
# Add this line:
# from handlers.model_logic import generate_combinations_excel
# generate_combinations_excel(st.session_state.products)
