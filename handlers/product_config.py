import streamlit as st
import pandas as pd

def load_product_controls():
    st.sidebar.header("🚀 Quick Setup")
    with st.sidebar.expander("1️⃣ Add / update products", True):
        pname = st.text_input("Product name")
        pwt   = st.number_input("Unit weight (kg)", 0.001, format="%.3f")
        pqty  = st.number_input("Quantity on shelf", 1, step=1)
        if st.button("➕ Add / Update"):
            if pname and pwt > 0:
                names = [p["name"] for p in st.session_state.products]
                if pname in names:
                    st.session_state.products[names.index(pname)].update(weight=pwt, quantity=pqty)
                    st.success(f"Updated {pname}")
                else:
                    st.session_state.products.append({"name": pname, "weight": pwt, "quantity": pqty})
                    st.success(f"Added {pname}")
                st.session_state.model = None
                st.session_state.trained_rows.clear()
            else:
                st.warning("Enter name and weight")
    with st.sidebar.expander("2️⃣ Current products", True):
        if st.session_state.products:
            st.dataframe(pd.DataFrame(st.session_state.products))
        else:
            st.info("No products yet")
