import os
import json
import hmac
import hashlib
from datetime import datetime, date

import pandas as pd
import streamlit as st
from supabase import create_client
import json

st.set_page_config(
    page_title="Croshia Admin Dashboard",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background: #fffaf7;
}
section[data-testid="stSidebar"] {
    background: #f8e8e5;
}
h1, h2, h3 {
    color: #793f51;
}
div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #f0d9d5;
    padding: 16px;
    border-radius: 12px;
}
.stButton > button {
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- CONFIGURATION ----------------

SUPABASE_URL = st.secrets.get(
    "SUPABASE_URL",
    os.getenv("SUPABASE_URL", "")
)

SUPABASE_KEY = st.secrets.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)

ADMIN_PASSWORD = st.secrets.get(
    "CROSHIA_ADMIN_PASSWORD",
    os.getenv("CROSHIA_ADMIN_PASSWORD", "")
)


# ---------------- DATABASE ----------------

@st.cache_resource
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def db():
    client = get_supabase()
    if client is None:
        st.error(
            "Supabase is not configured. Add SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in Streamlit Cloud Secrets."
        )
        st.stop()
    return client


def read_table(table, limit=1000):
    try:
        result = db().table(table).select("*").limit(limit).execute()
        return result.data or []
    except Exception as exc:
        st.error(f"Could not load {table}: {exc}")
        return []


def update_row(table, row_id, values):
    try:
        db().table(table).update(values).eq("id", row_id).execute()
        return True
    except Exception as exc:
        st.error(f"Could not update {table}: {exc}")
        return False


def insert_row(table, values):
    try:
        db().table(table).insert(values).execute()
        return True
    except Exception as exc:
        st.error(f"Could not add record to {table}: {exc}")
        return False


def delete_row(table, row_id):
    try:
        db().table(table).delete().eq("id", row_id).execute()
        return True
    except Exception as exc:
        st.error(f"Could not delete record from {table}: {exc}")
        return False


def money(value):
    try:
        return f"PKR {float(value or 0):,.0f}"
    except (ValueError, TypeError):
        return "PKR 0"


def safe_date(value):
    if not value:
        return "Not set"
    try:
        return str(value)[:10]
    except Exception:
        return "Not set"


def order_items(order):
    items = order.get("items_json", [])

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except (json.JSONDecodeError, TypeError):
            return []

    return items if isinstance(items, list) else []


# ---------------- LOGIN ----------------

if "croshia_admin_ok" not in st.session_state:
    st.session_state["croshia_admin_ok"] = False

if not ADMIN_PASSWORD:
    st.error(
        "Admin password is missing. Add CROSHIA_ADMIN_PASSWORD "
        "to Streamlit Cloud Secrets before using this dashboard."
    )
    st.stop()

if not st.session_state["croshia_admin_ok"]:
    st.markdown(
        "<h1 style='text-align:center;'>🧶 Croshia Studio</h1>"
        "<p style='text-align:center;'>Admin Dashboard</p>",
        unsafe_allow_html=True,
    )

    with st.form("admin_login"):
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        if hmac.compare_digest(password, ADMIN_PASSWORD):
            st.session_state["croshia_admin_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


# ---------------- SIDEBAR ----------------

st.sidebar.title("🧶 Croshia Studio")
st.sidebar.caption("Admin Management")

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "Orders",
        "Products",
        "Customers",
        "Settings",
    ],
)

if st.sidebar.button("Refresh dashboard", use_container_width=True):
    st.cache_resource.clear()
    st.rerun()

if st.sidebar.button("Log out", use_container_width=True):
    st.session_state["croshia_admin_ok"] = False
    st.rerun()


# ---------------- LOAD DATA ----------------

orders = read_table("orders")
products = read_table("products")
customers = read_table("customers")
settings_rows = read_table("settings")

orders_df = pd.DataFrame(orders)
products_df = pd.DataFrame(products)
customers_df = pd.DataFrame(customers)


# ---------------- OVERVIEW ----------------

if page == "Overview":
    st.title("Dashboard Overview")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")

    total_orders = len(orders)
    new_orders = sum(1 for o in orders if str(o.get("status", "")).lower() == "new")
    completed_orders = sum(
        1 for o in orders
        if str(o.get("status", "")).lower() == "completed"
    )
    total_customers = len(customers)
    active_products = sum(1 for p in products if p.get("active", True))

    completed_sales = sum(
        float(o.get("total_amount") or 0)
        for o in orders
        if str(o.get("status", "")).lower() == "completed"
    )

    total_cost = 0
    for order in orders:
        if str(order.get("status", "")).lower() != "completed":
            continue

        items = order_items(order)
        if isinstance(items, list):
            for item in items:
                try:
                    qty = int(item.get("quantity", item.get("qty", 1)))
                    product_id = item.get("product_id", item.get("id"))
                    product = next(
                        (
                            p for p in products
                            if str(p.get("id")) == str(product_id)
                        ),
                        None,
                    )
                    if product:
                        total_cost += float(product.get("cost") or 0) * qty
                except Exception:
                    pass

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Orders", total_orders)
    col2.metric("New Orders", new_orders)
    col3.metric("Completed Orders", completed_orders)

    col4, col5, col6 = st.columns(3)
    col4.metric("Completed Sales", money(completed_sales))
    col5.metric("Registered Customers", total_customers)
    col6.metric("Active Products", active_products)

    st.divider()
    st.subheader("Recent Orders")

    if orders:
        recent = sorted(
            orders,
            key=lambda o: str(o.get("created_at", "")),
            reverse=True,
        )[:10]

        recent_data = []
        for order in recent:
            recent_data.append({
                "Order Code": order.get("order_code", ""),
                "Customer": order.get("customer_name", ""),
                "Total": money(order.get("total_amount")),
                "Status": order.get("status", "New"),
                "Date": safe_date(order.get("created_at")),
            })

        st.dataframe(
            pd.DataFrame(recent_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No orders have been received yet.")

    st.subheader("Inventory")
    if products:
        inventory = [
            {
                "Product": p.get("name", ""),
                "Category": p.get("category", ""),
                "Price": money(p.get("price")),
                "Stock": p.get("stock", 0),
                "Active": p.get("active", True),
            }
            for p in products
        ]
        st.dataframe(
            pd.DataFrame(inventory),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Add products from the Products section.")


# ---------------- ORDERS ----------------

elif page == "Orders":
    st.title("Order Management")

    search = st.text_input(
        "Search orders",
        placeholder="Order code, customer, email, or phone",
    )

    filtered_orders = orders

    if search.strip():
        term = search.strip().lower()
        filtered_orders = [
            o for o in orders
            if term in str(o.get("order_code", "")).lower()
            or term in str(o.get("customer_name", "")).lower()
            or term in str(o.get("email", "")).lower()
            or term in str(o.get("phone", "")).lower()
        ]

    if not filtered_orders:
        st.info("No matching orders found.")
    else:
        for order in sorted(
            filtered_orders,
            key=lambda o: str(o.get("created_at", "")),
            reverse=True,
        ):
            order_id = order.get("id")
            order_code = order.get("order_code") or str(order_id)

            with st.expander(
                f"{order_code} — {order.get('customer_name', 'Customer')} — "
                f"{money(order.get('total_amount'))}"
            ):
                left, right = st.columns(2)

                with left:
                    st.write(f"**Customer:** {order.get('customer_name', '')}")
                    st.write(f"**Email:** {order.get('email', '')}")
                    st.write(f"**Phone:** {order.get('phone', '')}")
                    st.write(f"**Fulfillment:** {order.get('fulfillment', '')}")
                    st.write(f"**Address:** {order.get('address', '') or 'Not provided'}")
                    st.write(f"**Pickup details:** {order.get('pickup_note', '') or 'Not provided'}")

                with right:
                    st.write(f"**Subtotal:** {money(order.get('subtotal'))}")
                    st.write(f"**Delivery fee:** {money(order.get('delivery_fee'))}")
                    st.write(f"**Total:** {money(order.get('total_amount'))}")
                    st.write(f"**Payment method:** {order.get('payment_method', '')}")
                    st.write(f"**Payment status:** {order.get('payment_status', 'Pending')}")
                    st.write(f"**Order date:** {safe_date(order.get('created_at'))}")

               
st.write("**Order Items**")

items = order_items(order)

if isinstance(items, list) and items:
    item_rows = []

    for item in items:
        if isinstance(item, dict):
            quantity = int(item.get("qty", item.get("quantity", 1)))
            price = float(item.get("price", 0) or 0)

            item_rows.append({
                "Product": item.get("name", "Unknown Product"),
                "Quantity": quantity,
                "Price per Item": f"PKR {price:,.0f}",
                "Subtotal": f"PKR {price * quantity:,.0f}",
            })

    if item_rows:
        st.dataframe(
            item_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No readable item details found.")
 
elif items:
             st.write(items)

else:
        st.info("No item details saved.")


statuses = [
                    "New",
                    "Discussing",
                    "In Progress",
                    "Waiting for Customer",
                    "Completed",
                    "Cancelled",
                ]

payment_statuses = [
                    "Pending",
                    "Paid",
                    "Failed",
                    "Refunded",
                ]

current_status = order.get("status", "New")
current_payment = order.get("payment_status", "Pending")

if current_status not in statuses:
                    current_status = "New"
if current_payment not in payment_statuses:
                    current_payment = "Pending"

with st.form(f"order_form_{order_id}"):
                    new_status = st.selectbox(
                        "Order status",
                        statuses,
                        index=statuses.index(current_status),
                    )

                    new_payment_status = st.selectbox(
                        "Payment status",
                        payment_statuses,
                        index=payment_statuses.index(current_payment),
                    )

                    admin_message = st.text_area(
                        "Message for customer",
                        value=order.get("admin_message") or "",
                        placeholder="Example: Your handmade order will be ready in 5 days.",
                    )

                    expected_date = st.text_input(
                        "Expected completion/delivery date (YYYY-MM-DD)",
                        value=str(order.get("expected_date") or "")[:10],
                    )

                    save_order = st.form_submit_button(
                        "Save order changes",
                        use_container_width=True,
                    )

if save_order:
                    if expected_date.strip():
                        try:
                            date.fromisoformat(expected_date.strip())
                        except ValueError:
                            st.error("Enter the date as YYYY-MM-DD.")
                            st.stop()

                    updated = update_row(
                        "orders",
                        order_id,
                        {
                            "status": new_status,
                            "payment_status": new_payment_status,
                            "admin_message": admin_message.strip(),
                            "expected_date": expected_date.strip() or None,
                        },
                    )

                    if updated:
                        st.success("Order updated.")
                        st.rerun()


# ---------------- PRODUCTS ----------------

elif page == "Products":
    st.title("Product Management")

    with st.expander("➕ Add a new product", expanded=not products):
        with st.form("add_product_form", clear_on_submit=True):
            name = st.text_input("Product name")
            category = st.selectbox(
                "Category",
                [
                    "Crochet Flowers",
                    "Keychains",
                    "Plushies",
                    "Accessories",
                    "Home Decor",
                    "Custom Designs",
                    "Other",
                ],
            )
            description = st.text_area("Description")
            price = st.number_input("Selling price (PKR)", min_value=0.0, step=50.0)
            cost = st.number_input("Estimated cost (PKR)", min_value=0.0, step=50.0)
            stock = st.number_input("Stock quantity", min_value=0, step=1)
            image_url = st.text_input("Image URL (optional)")
            active = st.checkbox("Visible in customer store", value=True)

            add_product = st.form_submit_button(
                "Add product",
                use_container_width=True,
            )

        if add_product:
            if not name.strip():
                st.error("Enter a product name.")
            else:
                success = insert_row(
                    "products",
                    {
                        "name": name.strip(),
                        "category": category,
                        "description": description.strip(),
                        "price": float(price),
                        "cost": float(cost),
                        "stock": int(stock),
                        "image_url": image_url.strip() or None,
                        "active": bool(active),
                    },
                )
                if success:
                    st.success("Product added.")
                    st.rerun()

    st.divider()
    st.subheader("Existing Products")

    if not products:
        st.info("No products have been added yet.")
    else:
        for product in products:
            product_id = product.get("id")

            with st.expander(
                f"{product.get('name', 'Product')} — "
                f"{money(product.get('price'))}"
            ):
                if product.get("image_url"):
                    st.image(product["image_url"], width=180)

                with st.form(f"product_form_{product_id}"):
                    p_name = st.text_input(
                        "Product name",
                        value=product.get("name") or "",
                    )
                    p_category = st.text_input(
                        "Category",
                        value=product.get("category") or "",
                    )
                    p_description = st.text_area(
                        "Description",
                        value=product.get("description") or "",
                    )
                    p_price = st.number_input(
                        "Price (PKR)",
                        min_value=0.0,
                        value=float(product.get("price") or 0),
                        step=50.0,
                    )
                    p_cost = st.number_input(
                        "Estimated cost (PKR)",
                        min_value=0.0,
                        value=float(product.get("cost") or 0),
                        step=50.0,
                    )
                    p_stock = st.number_input(
                        "Stock",
                        min_value=0,
                        value=int(product.get("stock") or 0),
                        step=1,
                    )
                    p_image = st.text_input(
                        "Image URL",
                        value=product.get("image_url") or "",
                    )
                    p_active = st.checkbox(
                        "Visible in customer store",
                        value=bool(product.get("active", True)),
                    )

                    save_product = st.form_submit_button(
                        "Save product changes",
                        use_container_width=True,
                    )

                if save_product:
                    if not p_name.strip():
                        st.error("Product name cannot be empty.")
                    else:
                        success = update_row(
                            "products",
                            product_id,
                            {
                                "name": p_name.strip(),
                                "category": p_category.strip(),
                                "description": p_description.strip(),
                                "price": float(p_price),
                                "cost": float(p_cost),
                                "stock": int(p_stock),
                                "image_url": p_image.strip() or None,
                                "active": bool(p_active),
                            },
                        )
                        if success:
                            st.success("Product updated.")
                            st.rerun()

                st.caption(
                    f"Estimated profit per item: "
                    f"{money(float(product.get('price') or 0) - float(product.get('cost') or 0))}"
                )

                if st.button(
                    "Delete product",
                    key=f"delete_product_{product_id}",
                    type="secondary",
                ):
                    if delete_row("products", product_id):
                        st.success("Product deleted.")
                        st.rerun()


# ---------------- CUSTOMERS ----------------

elif page == "Customers":
    st.title("Customer Management")

    if customers:
        display_customers = [
            {
                "Name": c.get("name", ""),
                "Email": c.get("email", ""),
                "Created": safe_date(c.get("created_at")),
            }
            for c in customers
        ]

        customer_df = pd.DataFrame(display_customers)
        st.dataframe(
            customer_df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download customer CSV",
            data=customer_df.to_csv(index=False).encode("utf-8"),
            file_name="croshia_customers.csv",
            mime="text/csv",
        )
    else:
        st.info("No registered customers yet.")


# ---------------- SETTINGS ----------------

elif page == "Settings":
    st.title("Store Settings")
    st.caption("These settings are shared through your Supabase database.")

    settings_map = {
        str(row.get("key")): row
        for row in settings_rows
        if row.get("key") is not None
    }

    def setting_value(key, default=""):
        row = settings_map.get(key)
        return str(row.get("value", default)) if row else str(default)

    with st.form("store_settings_form"):
        store_name = st.text_input(
            "Store name",
            value=setting_value("store_name", "Croshia Studio"),
        )

        about = st.text_area(
            "Store description",
            value=setting_value("about", "Handmade crochet designs made with care."),
        )

        try:
            delivery_fee_default = float(
                setting_value("delivery_fee", "150")
            )
        except ValueError:
            delivery_fee_default = 150.0

        delivery_fee = st.number_input(
            "Delivery fee (PKR)",
            min_value=0.0,
            value=delivery_fee_default,
            step=50.0,
        )

        delivery_enabled = st.checkbox(
            "Enable delivery",
            value=setting_value("delivery_enabled", "true").lower() == "true",
        )

        pickup_enabled = st.checkbox(
            "Enable pickup",
            value=setting_value("pickup_enabled", "true").lower() == "true",
        )

        pickup_note = st.text_area(
            "Pickup instructions",
            value=setting_value("pickup_note", ""),
        )

        save_settings = st.form_submit_button(
            "Save store settings",
            use_container_width=True,
        )

    if save_settings:
        settings_to_save = {
            "store_name": store_name.strip(),
            "about": about.strip(),
            "delivery_fee": str(float(delivery_fee)),
            "delivery_enabled": str(delivery_enabled).lower(),
            "pickup_enabled": str(pickup_enabled).lower(),
            "pickup_note": pickup_note.strip(),
        }

        failed = False

        for key, value in settings_to_save.items():
            existing = settings_map.get(key)

            try:
                if existing:
                    db().table("settings").update(
                        {"value": value}
                    ).eq("key", key).execute()
                else:
                    db().table("settings").insert(
                        {"key": key, "value": value}
                    ).execute()
            except Exception as exc:
                failed = True
                st.error(f"Could not save setting '{key}': {exc}")

        if not failed:
            st.success("Store settings saved.")
            st.rerun()

    st.divider()
    st.subheader("Database Status")
    st.write("Connected project:", SUPABASE_URL)
    st.write("Orders loaded:", len(orders))
    st.write("Products loaded:", len(products))
    st.write("Customers loaded:", len(customers))

    st.warning(
        "Keep your SUPABASE_SERVICE_ROLE_KEY private. "
        "Never place it in public code or share it with customers."
    )
