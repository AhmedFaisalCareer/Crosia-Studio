
import streamlit as st
import sqlite3
import json
import os
import secrets


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "croshia.db"
)

DB_PATH = os.path.join(os.path.dirname(__file__), "croshia.db")
ADMIN_PASSWORD = os.getenv("CROSHIA_ADMIN_PASSWORD", "change-this-password")

st.set_page_config(
    page_title="Croshia Admin",
    page_icon="🧶",
    layout="wide"
)

def get_db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con

st.title("🧶 Croshia Studio Admin")

if not st.session_state.get("logged_in", False):
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if username.strip() == "admin" and secrets.compare_digest(
            password, ADMIN_PASSWORD
        ):
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.stop()

if st.button("Log out"):
    st.session_state.logged_in = False
    st.rerun()

with get_db() as con:
    orders = con.execute(
        "SELECT * FROM orders ORDER BY id DESC"
    ).fetchall()

    products = con.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

col1, col2, col3 = st.columns(3)
col1.metric("Total Orders", len(orders))
col2.metric(
    "Pending Orders",
    sum(o["status"] == "Pending" for o in orders)
)
col3.metric(
    "Paid Revenue",
    f"PKR {sum(o['total_amount'] for o in orders if o['payment_status'] == 'Paid' and o['status'] != 'Cancelled'):,.0f}"
)

st.subheader("Customer Orders")

for order in orders:
    with st.expander(
        f"{order['order_code']} · {order['customer_name']} · "
        f"PKR {order['total_amount']:,.0f} · {order['status']}"
    ):
        st.write("Email:", order["email"])
        st.write("Phone:", order["phone"])
        st.write("Fulfillment:", order["fulfillment"])
        st.write("Address:", order["address"])
        st.write("Payment method:", order["payment_method"])

        try:
            for item in json.loads(order["items_json"]):
                st.write(
                    f"{item['name']} × {item['qty']} — "
                    f"PKR {item['price'] * item['qty']:,.0f}"
                )
        except (ValueError, TypeError, KeyError):
            st.warning("Could not read order items.")

        with st.form(f"update_{order['id']}"):
            status_options = [
                "Pending", "Processing", "Making",
                "Ready for Pickup", "Shipped",
                "Delivered", "Cancelled"
            ]
            payment_options = [
                "Unpaid", "Payment Submitted", "Paid", "Refunded"
            ]

            status = st.selectbox(
                "Order status",
                status_options,
                index=status_options.index(order["status"])
                if order["status"] in status_options else 0
            )

            payment = st.selectbox(
                "Payment status",
                payment_options,
                index=payment_options.index(order["payment_status"])
                if order["payment_status"] in payment_options else 0
            )

            message = st.text_area(
                "Customer message",
                value=order["admin_message"] or ""
            )

            expected = st.text_input(
                "Expected date (YYYY-MM-DD)",
                value=order["expected_date"] or ""
            )

            if st.form_submit_button("Save Update"):
                with get_db() as con:
                    con.execute("""
                        UPDATE orders
                        SET status=?, payment_status=?,
                            admin_message=?, expected_date=?
                        WHERE id=?
                    """, (
                        status, payment, message.strip(),
                        expected.strip(), order["id"]
                    ))

                st.success("Order updated.")
                st.rerun()

st.subheader("Products & Inventory")

for product in products:
    st.write(
        f"**{product['name']}** — "
        f"PKR {product['price']:,.0f} · "
        f"Stock: {product['stock']}"
    )
