import os
import json
import hmac
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# Croshia Studio Admin Dashboard
# IMPORTANT: This SQLite version works only when it can access the SAME croshia.db
# file as the customer app. Separate Streamlit Cloud deployments do not share files.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("CROSHIA_DB_PATH", str(BASE_DIR / "croshia.db")))
ADMIN_PASSWORD = os.getenv("CROSHIA_ADMIN_PASSWORD", "change-this-password")

st.set_page_config(
    page_title="Croshia Studio | Admin",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');
.stApp {background:#FFFAF6;color:#332A31;font-family:'DM Sans',sans-serif}
h1,h2,h3 {font-family:'Playfair Display',serif!important}
h1 {color:#985B75!important}
.block-container {max-width:1400px;padding-top:1.5rem;padding-bottom:3rem}
div.stButton>button,div.stFormSubmitButton>button {border-radius:10px;font-weight:650;min-height:2.5rem}
div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"] {background:#985B75;color:white;border:0}
[data-testid="stMetric"] {background:#fff;border:1px solid #EFDEE5;padding:14px;border-radius:14px}
.admin-hero {background:linear-gradient(115deg,#F3DFE7,#FFF5ED);padding:24px;border-radius:18px;margin:8px 0 20px}
.small-note {color:#725F68;font-size:.9rem}
</style>
""", unsafe_allow_html=True)


def connect():
    con = sqlite3.connect(str(DB_PATH), timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=20000")
    return con


def tables_available():
    if not DB_PATH.exists():
        return set()
    with connect() as con:
        return {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}


def columns(table):
    with connect() as con:
        return {r["name"] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()}


def safe_df(sql, params=()):
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


def money(value):
    try:
        return f"PKR {float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "PKR 0"


def set_order_fields(order_id, status, payment_status, admin_message, expected_date):
    cols = columns("orders")
    updates, values = [], []
    if "status" in cols:
        updates.append('"status"=?'); values.append(status)
    elif "order_status" in cols:
        updates.append('"order_status"=?'); values.append(status)
    if "payment_status" in cols:
        updates.append('"payment_status"=?'); values.append(payment_status)
    if "admin_message" in cols:
        updates.append('"admin_message"=?'); values.append(admin_message.strip())
    if "expected_date" in cols:
        updates.append('"expected_date"=?'); values.append(expected_date.strip())
    elif "estimated_days" in cols:
        try:
            days = max(1, int(expected_date))
        except (TypeError, ValueError):
            days = 7
        updates.append('"estimated_days"=?'); values.append(days)
    if "updated_at" in cols:
        updates.append('"updated_at"=?'); values.append(datetime.now().isoformat(timespec="seconds"))
    if not updates:
        return
    values.append(order_id)
    with connect() as con:
        con.execute(f'UPDATE orders SET {", ".join(updates)} WHERE id=?', values)
        con.commit()


def login():
    st.markdown('<div class="admin-hero"><h1>🧶 Croshia Studio</h1><p>Private store management dashboard</p></div>', unsafe_allow_html=True)
    st.subheader("Admin sign in")
    with st.form("admin_login"):
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        if ADMIN_PASSWORD == "change-this-password":
            st.error("Set CROSHIA_ADMIN_PASSWORD in your deployment secrets/environment before using this dashboard.")
        elif hmac.compare_digest(password, ADMIN_PASSWORD):
            st.session_state["croshia_admin_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")


if "croshia_admin_ok" not in st.session_state:
    st.session_state["croshia_admin_ok"] = False

if not st.session_state["croshia_admin_ok"]:
    login()
    st.stop()

with st.sidebar:
    st.markdown("## 🧶 Croshia Admin")
    st.caption("Handmade store management")
    page = st.radio("Navigate", ["Overview", "Orders", "Products", "Customers", "Settings"])
    if st.button("Sign out", use_container_width=True):
        st.session_state["croshia_admin_ok"] = False
        st.rerun()

st.title(page)

available = tables_available()
required = {"orders", "products"}
if not DB_PATH.exists() or not required.issubset(available):
    st.error(f"Database not found or missing tables: {DB_PATH}")
    st.warning(
        "This app needs the same croshia.db file used by the customer app. "
        "It will not see data from a separate Streamlit Cloud deployment's local SQLite database."
    )
    st.stop()

order_cols = columns("orders")
product_cols = columns("products")

if page == "Overview":
    orders = safe_df("SELECT * FROM orders ORDER BY id DESC")
    products = safe_df("SELECT * FROM products")
    customers = safe_df("SELECT * FROM customers") if "customers" in available else pd.DataFrame()
    status_col = "status" if "status" in orders.columns else ("order_status" if "order_status" in orders.columns else None)
    total_col = "total_amount" if "total_amount" in orders.columns else ("total" if "total" in orders.columns else None)
    completed = orders[orders[status_col].astype(str).str.lower().eq("completed")] if status_col and not orders.empty else orders.iloc[0:0]
    revenue = completed[total_col].sum() if total_col and not completed.empty else 0
    active_count = int((~orders[status_col].astype(str).str.lower().isin(["completed", "cancelled"])).sum()) if status_col and not orders.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total orders", len(orders))
    c2.metric("Active orders", active_count)
    c3.metric("Completed orders", len(completed))
    c4.metric("Completed sales", money(revenue))
    st.caption("Sales count as revenue only when an order is marked Completed. Profit depends on the product costs you enter.")
    left, right = st.columns(2)
    with left:
        st.subheader("Recent orders")
        if not orders.empty:
            display_cols = [c for c in ["order_code", "customer_name", "email", status_col, total_col, "created_at"] if c and c in orders.columns]
            st.dataframe(orders[display_cols].head(8), use_container_width=True, hide_index=True)
        else:
            st.info("No orders yet.")
    with right:
        st.subheader("Products and stock")
        if not products.empty:
            display_cols = [c for c in ["name", "category", "price", "stock", "active"] if c in products.columns]
            st.dataframe(products[display_cols].head(10), use_container_width=True, hide_index=True)
        else:
            st.info("No products found.")

elif page == "Orders":
    orders = safe_df("SELECT * FROM orders ORDER BY id DESC")
    if orders.empty:
        st.info("No orders have been placed yet.")
    else:
        search = st.text_input("Search by order code, customer, email, or phone")
        if search:
            mask = pd.Series(False, index=orders.index)
            for col in ["order_code", "customer_name", "email", "phone"]:
                if col in orders.columns:
                    mask |= orders[col].fillna("").astype(str).str.contains(search, case=False, regex=False)
            orders = orders[mask]
        status_col = "status" if "status" in orders.columns else ("order_status" if "order_status" in orders.columns else None)
        for _, order in orders.iterrows():
            order_id = int(order["id"])
            code = str(order.get("order_code", f"#{order_id}"))
            with st.expander(f"{code} · {order.get('customer_name', 'Customer')} · {money(order.get('total_amount', order.get('total', 0)))}"):
                a, b = st.columns(2)
                with a:
                    st.write(f"**Customer:** {order.get('customer_name', '')}")
                    st.write(f"**Email:** {order.get('email', '')}")
                    st.write(f"**Phone:** {order.get('phone', '')}")
                    st.write(f"**Fulfilment:** {order.get('fulfillment', '')}")
                    st.write(f"**Address:** {order.get('address', '') or '—'}")
                    st.write(f"**Pickup details:** {order.get('pickup_note', '') or '—'}")
                with b:
                    st.write(f"**Payment method:** {order.get('payment_method', '')}")
                    st.write(f"**Payment status:** {order.get('payment_status', '')}")
                    st.write(f"**Total:** {money(order.get('total_amount', order.get('total', 0)))}")
                    st.write(f"**Placed:** {order.get('created_at', '')}")
                try:
                    items = json.loads(order.get("items_json", "[]") or "[]")
                    if isinstance(items, list) and items:
                        st.write("**Items**")
                        for item in items:
                            st.write(f"• {item.get('name', item.get('title', 'Item'))} × {item.get('quantity', 1)}")
                except (TypeError, json.JSONDecodeError):
                    st.caption("Order items could not be decoded.")
                current_status = str(order.get(status_col, "Pending")) if status_col else "Pending"
                status_options = ["New", "Pending", "Confirmed", "Preparing", "Ready", "Completed", "Cancelled"]
                if current_status not in status_options:
                    status_options.insert(0, current_status)
                with st.form(f"update_order_{order_id}"):
                    new_status = st.selectbox("Order status", status_options, index=status_options.index(current_status))
                    current_payment = str(order.get("payment_status", "Unpaid"))
                    payment_options = ["Unpaid", "Pending", "Paid", "Failed", "Refunded", current_payment]
                    payment_options = list(dict.fromkeys(payment_options))
                    new_payment = st.selectbox("Payment status", payment_options, index=payment_options.index(current_payment))
                    message = st.text_area("Message for customer", value=str(order.get("admin_message", "") or ""), help="This is saved to the order. It will appear to customers only if the customer app displays this field.")
                    if "expected_date" in order.index:
                        expected = st.text_input("Expected completion date (e.g. 2026-11-01)", value=str(order.get("expected_date", "") or ""))
                    else:
                        expected = st.text_input("Estimated days until completion", value=str(order.get("estimated_days", 7) or 7))
                    save = st.form_submit_button("Save order update", type="primary")
                if save:
                    set_order_fields(order_id, new_status, new_payment, message, expected)
                    st.success("Order updated.")
                    st.rerun()

elif page == "Products":
    st.subheader("Add a product/design")
    with st.form("add_product", clear_on_submit=True):
        name = st.text_input("Design name")
        category = st.text_input("Category", value="Crochet")
        description = st.text_area("Description")
        col1, col2, col3 = st.columns(3)
        with col1:
            price = st.number_input("Selling price (PKR)", min_value=0.0, value=700.0, step=50.0)
        with col2:
            cost = st.number_input("Material/labour cost (PKR)", min_value=0.0, value=0.0, step=50.0)
        with col3:
            stock = st.number_input("Stock quantity", min_value=0, value=10, step=1)
        image_url = st.text_input("Image URL (optional)")
        add = st.form_submit_button("Add design", type="primary")
    if add:
        if not name.strip():
            st.error("Please enter a design name.")
        else:
            now = datetime.now().isoformat(timespec="seconds")
            cols = product_cols
            fields, vals = ["name"], [name.strip()]
            for col, val in [("category", category.strip() or "Crochet"), ("description", description.strip()), ("price", price), ("cost", cost), ("stock", stock), ("image_url", image_url.strip()), ("active", 1), ("created_at", now)]:
                if col in cols:
                    fields.append(col); vals.append(val)
            with connect() as con:
                con.execute(f"INSERT INTO products ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})", vals)
                con.commit()
            st.success("Design added.")
            st.rerun()
    st.divider()
    st.subheader("Existing designs")
    products = safe_df("SELECT * FROM products ORDER BY id DESC")
    if products.empty:
        st.info("No products found.")
    else:
        for _, product in products.iterrows():
            pid = int(product["id"])
            with st.expander(f"{product.get('name', 'Design')} · {money(product.get('price', 0))}"):
                with st.form(f"product_{pid}"):
                    pname = st.text_input("Name", value=str(product.get("name", "")))
                    pcategory = st.text_input("Category", value=str(product.get("category", "Crochet")))
                    pdescription = st.text_area("Description", value=str(product.get("description", "")))
                    pprice = st.number_input("Price (PKR)", min_value=0.0, value=float(product.get("price", 0) or 0), step=50.0)
                    pcost = st.number_input("Cost (PKR)", min_value=0.0, value=float(product.get("cost", 0) or 0), step=50.0)
                    pstock = st.number_input("Stock", min_value=0, value=int(product.get("stock", 0) or 0), step=1)
                    pactive = st.checkbox("Visible in store", value=bool(product.get("active", 1)))
                    pimage = st.text_input("Image URL", value=str(product.get("image_url", "") or ""))
                    update = st.form_submit_button("Save design changes", type="primary")
                if update:
                    fields, vals = [], []
                    for col, val in [("name", pname.strip()), ("category", pcategory.strip() or "Crochet"), ("description", pdescription.strip()), ("price", pprice), ("cost", pcost), ("stock", pstock), ("active", int(pactive)), ("image_url", pimage.strip())]:
                        if col in product_cols:
                            fields.append(f'"{col}"=?'); vals.append(val)
                    if fields:
                        vals.append(pid)
                        with connect() as con:
                            con.execute(f"UPDATE products SET {','.join(fields)} WHERE id=?", vals)
                            con.commit()
                    st.success("Design saved.")
                    st.rerun()
                if "image_url" in product.index and product.get("image_url"):
                    st.image(str(product.get("image_url")), width=180)

elif page == "Customers":
    if "customers" not in available:
        st.info("This database does not have a customers table.")
    else:
        customers = safe_df("SELECT id, name, email, created_at FROM customers ORDER BY id DESC")
        st.metric("Registered customers", len(customers))
        if customers.empty:
            st.info("No customer accounts registered yet.")
        else:
            st.dataframe(customers, use_container_width=True, hide_index=True)
            st.download_button("Download customer list (CSV)", customers.to_csv(index=False).encode("utf-8"), "croshia_customers.csv", "text/csv")

elif page == "Settings":
    st.subheader("Store database")
    st.write(f"**Database path:** `{DB_PATH}`")
    st.write(f"**Tables found:** {', '.join(sorted(available))}")
    st.info("This admin app uses the same SQLite schema as the current Croshia customer app. Separate hosted apps need a shared cloud database to see each other's records.")
    st.subheader("Profit estimate")
    products = safe_df("SELECT * FROM products")
    if not products.empty and {"price", "cost"}.issubset(products.columns):
        products["estimated_profit_per_item"] = products["price"].fillna(0) - products["cost"].fillna(0)
        st.dataframe(products[[c for c in ["name", "price", "cost", "estimated_profit_per_item", "stock"] if c in products.columns]], use_container_width=True, hide_index=True)
