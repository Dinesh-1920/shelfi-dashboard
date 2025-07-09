# handlers/quantity_logic.py

WEIGHT_THRESHOLD = 0.02  # 20 grams threshold for load cell noise

def detect_action(delta):
    if abs(delta) < WEIGHT_THRESHOLD:
        return "NPT"
    return "Kept" if delta > 0 else "Taken"

def update_quantity_tracker(qty_tracker, action, predicted_product):
    if predicted_product not in qty_tracker:
        return qty_tracker

    if action == "Taken":
        qty_tracker[predicted_product] = max(0, qty_tracker[predicted_product] - 1)
    elif action == "Kept":
        qty_tracker[predicted_product] += 1

    return qty_tracker
