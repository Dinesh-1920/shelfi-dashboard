# 📁 File: handlers/combo_generator.py
import pandas as pd
import itertools

def generate_combinations_excel(products, output_path="combinations.xlsx"):
    """
    Generate all meaningful weight combinations based on product quantities and weights.
    Save to Excel.
    """
    product_names = [p["name"] for p in products]
    product_weights = {p["name"]: p["weight"] for p in products}
    product_quantities = {p["name"]: p["quantity"] for p in products}

    combinations = []

    # Generate all combinations
    for r in range(1, len(products) + 1):
        for prod_combo in itertools.combinations(products, r):
            name_combo = [p["name"] for p in prod_combo]
            # Generate count combos based on individual product's quantity limits
            qty_ranges = [range(1, product_quantities[name] + 1) for name in name_combo]
            for counts in itertools.product(*qty_ranges):
                combo_label = "+".join(f"{n}" * c for n, c in zip(name_combo, counts))
                total_weight = sum(product_weights[n] * c for n, c in zip(name_combo, counts))
                combinations.append({"Combination": combo_label, "Total Weight": total_weight})

    df = pd.DataFrame(combinations)
    df.to_excel(output_path, index=False)
    print(f"✅ Excel with {len(df)} combinations saved to {output_path}")
