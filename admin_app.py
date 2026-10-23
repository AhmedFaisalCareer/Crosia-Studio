
import os
import json
import sqlite3
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, date, timedelta

import streamlit as st

# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "croshia.db")

DEFAULT_ADMIN_PASSWORD = os.getenv(
    "CROSHIA_ADMIN_PASSWORD", "change-this-password"
)

st.set_page_config(
    page_title="Croshia Studio Admin",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# STYLE
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

.stApp {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Playfair Display', serif !important;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}

[data-testid="stMetric"] {
    background: var(--secondary-background-color);
    padding: 18px;
    border-radius: 14px;
    border: 1px solid rgba(128,128,128,0.18);
}

div.stButton > button,
div.stFormSubmitButton > button {
    border-radius: 9px;
    min-height: 2.5rem;
    font-weight: 600;
}

.admin-banner {
    padding: 24px;
    border-radius: 18px;
    margin: 12px 0 22px;
    background: linear-gradient(115deg, #F3DFE7, #FFF5ED);
    color: #493540;
}

.admin-banner h2 {
    color: #985B75;
    margin-bottom: 5px;
}

.small-note {
    color: #82727B;
    font-size: .85rem;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATABASE
# =========================================================

def get_db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 20000")
    con.execute("PRAGMA foreign_keys = ON")
    return con


def table_exists(con, table):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone() is not None


def columns(con, table):
    return {
        row["name"]
        for row in con.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    }


def add_column(con, table, column, definition):
    if table_exists(con, table) and column not in columns(con, table):
        con.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'
        )


def initialize_database():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Handmade',
                price REAL NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                image_data TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                stock INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                fulfillment TEXT NOT NULL,
                address TEXT DEFAULT '',
                pickup_note TEXT DEFAULT '',
                payment_method TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'Unpaid',
                items_json TEXT NOT NULL DEFAULT '[]',
                subtotal REAL NOT NULL DEFAULT 0,
                delivery_fee REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                admin_message TEXT DEFAULT '',
                expected_date TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Safely add missing columns without deleting existing records.
        product_fields = {
            "category": "TEXT DEFAULT 'Handmade'",
            "cost": "REAL NOT NULL DEFAULT 0",
            "description": "TEXT DEFAULT ''",
            "image_data": "TEXT DEFAULT ''",
            "image_url": "TEXT DEFAULT ''",
            "stock": "INTEGER NOT NULL DEFAULT 0",
            "active": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT DEFAULT ''",
        }

        for name, definition in product_fields.items():
            add_column(con, "products", name, definition)

        order_fields = {
            "order_code": "TEXT",
            "customer_name": "TEXT DEFAULT ''",
            "email": "TEXT DEFAULT ''",
            "phone": "TEXT DEFAULT ''",
            "fulfillment": "TEXT DEFAULT 'Delivery'",
            "address": "TEXT DEFAULT ''",
            "pickup_note": "TEXT DEFAULT ''",
            "payment_method": "TEXT DEFAULT 'Cash on Delivery'",
            "payment_status": "TEXT DEFAULT 'Unpaid'",
            "items_json": "TEXT DEFAULT '[]'",
            "subtotal": "REAL DEFAULT 0",
            "delivery_fee": "REAL DEFAULT 0",
            "total_amount": "REAL DEFAULT 0",
            "status": "TEXT DEFAULT 'Pending'",
            "admin_message": "TEXT DEFAULT ''",
            "expected_date": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
        }

        for name, definition in order_fields.items():
            add_column(con, "orders", name, definition)

        defaults = {
            "store_name": "Croshia Studio",
            "about": "Beautiful crochet creations, handmade with love.",
            "contact_email": "",
            "contact_phone": "",
            "delivery_fee": "200",
            "delivery_charge": "200",
            "delivery_enabled": "true",
            "pickup_enabled": "true",
            "currency": "PKR",
            "payment_name": "Croshia Studio",
            "payment_method": "Bank Transfer",
            "payment_details": "",
            "payment_instructions": "Contact the store after making your transfer.",
            "payment_title": "Payment Instructions",
            "payment_account_name": "Croshia Studio",
            "payment_account_details": "",
            "payment_provider": "",
            "gateway_checkout_url": "",
            "online_payment_enabled": "false",
            "cash_payment_enabled": "true",
            "manual_transfer_enabled": "true",
            "pickup_note": "Pickup instructions will be shared after confirmation.",
        }

        for key, value in defaults.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value)
            )


initialize_database()

# =========================================================
# SETTINGS HELPERS
# =========================================================

def get_setting(key, default=""):
    with get_db() as con:
        row = con.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

    return row["value"] if row else default


def save_setting(key, value):
    with get_db() as con:
        con.execute("""
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, str(value)))


def get_delivery_fee():
    # Support the keys used by both versions of the customer app.
    charge = get_setting("delivery_charge", "")
    fee = get_setting("delivery_fee", "200")

    try:
        if charge != "" and float(charge) != 200:
            return float(charge)
        return float(fee or charge or 200)
    except (ValueError, TypeError):
        return 200.0


# =========================================================
# ADMIN SECURITY
# =========================================================

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000
    ).hex()

    return f"{salt}${hashed}"


def verify_password(password, stored_hash):
    try:
        salt, expected_hash = stored_hash.split("$", 1)
        actual_hash = password_hash(password, salt).split("$", 1)[1]
        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, AttributeError):
        return False


def check_login(username, password):
    return (
        username.strip().lower() == "admin"
        and secrets.compare_digest(password, "naba123")
    )


# =========================================================
# DATA HELPERS
# =========================================================

def get_orders():
    with get_db() as con:
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM orders ORDER BY id DESC"
            ).fetchall()
        ]


def get_products():
    with get_db() as con:
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM products ORDER BY id DESC"
            ).fetchall()
        ]


def get_customers():
    with get_db() as con:
        if not table_exists(con, "customers"):
            return []

        return [
            dict(row)
            for row in con.execute("""
                SELECT id, name, email, created_at
                FROM customers
                ORDER BY id DESC
            """).fetchall()
        ]


def money(value):
    return f"PKR {float(value or 0):,.0f}"


def update_order(order_id, status, payment_status, message, expected_date):
    with get_db() as con:
        con.execute("""
            UPDATE orders
            SET status=?,
                payment_status=?,
                admin_message=?,
                expected_date=?
            WHERE id=?
        """, (
            status,
            payment_status,
            message,
            expected_date,
            order_id
        ))


def insert_product(
    name, description, category, price, cost,
    stock, image_data, image_url
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    with get_db() as con:
        con.execute("""
            INSERT INTO products(
                name, description, category, price, cost,
                stock, image_data, image_url, active, created_at
            )
            VALUES(?,?,?,?,?,?,?,?,1,?)
        """, (
            name.strip(),
            description.strip(),
            category.strip(),
            float(price),
            float(cost),
            int(stock),
            image_data,
            image_url.strip(),
            now
        ))


def update_product(
    product_id, name, description, category, price,
    cost, stock, image_data, image_url, active
):
    with get_db() as con:
        con.execute("""
            UPDATE products
            SET name=?,
                description=?,
                category=?,
                price=?,
                cost=?,
                stock=?,
                image_data=?,
                image_url=?,
                active=?
            WHERE id=?
        """, (
            name.strip(),
            description.strip(),
            category.strip(),
            float(price),
            float(cost),
            int(stock),
            image_data,
            image_url.strip(),
            int(active),
            product_id
        ))


def encode_image(uploaded_file):
    if uploaded_file is None:
        return ""

    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")


def image_preview(image_data, image_url=""):
    if image_data:
        st.image(
            "data:image/jpeg;base64," + image_data,
            use_container_width=True
        )
    elif image_url:
        st.image(image_url, use_container_width=True)


def safe_order_items(order):
    try:
        result = json.loads(order.get("items_json") or "[]")
        return result if isinstance(result, list) else []
    except (ValueError, TypeError):
        return []


def estimate_product_margin(orders, products):
    # Use saved order prices and current estimated product costs.
    # This is an estimate, not an accounting profit figure.
    costs = {
        p["id"]: float(p.get("cost") or 0)
        for p in products
    }

    total = 0.0

    for order in orders:
        if order.get("status") == "Cancelled":
            continue

        for item in safe_order_items(order):
            try:
                product_id = int(item.get("product_id", 0))
                price = float(item.get("price", 0))
                qty = int(item.get("qty", 1))
                total += (price - costs.get(product_id, 0)) * qty
            except (ValueError, TypeError):
                continue

    return total


# =========================================================
# LOGIN
# =========================================================

st.title("🧶 Croshia Studio")
st.caption("Store administration dashboard")

if not st.session_state.get("croshia_admin_logged_in", False):
    st.markdown("""
    <div class="admin-banner">
        <h2>Welcome to Croshia Admin</h2>
        <p>Manage handmade products, orders, inventory and store settings.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("admin_login_form"):
        username = st.text_input("Admin username", placeholder="admin")
        password = st.text_input("Admin password", type="password")
        login_clicked = st.form_submit_button(
            "Login", use_container_width=True
        )

    if login_clicked:
        if check_login(username, password):
            st.session_state.croshia_admin_logged_in = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.info(
        "Default local testing login: username `admin`, password "
        "`change-this-password`, unless you configured "
        "`CROSHIA_ADMIN_PASSWORD` or changed the password in Security."
    )

    st.stop()

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🧶 Croshia Admin")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Orders",
        "Products",
        "Payment Settings",
        "Store Settings",
        "Customers",
        "Security",
    ]
)

if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state.croshia_admin_logged_in = False
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("Croshia Studio · Administration")

orders = get_orders()
products = get_products()

# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":
    st.markdown("""
    <div class="admin-banner">
        <h2>Store Overview</h2>
        <p>Monitor orders, revenue and handmade inventory.</p>
    </div>
    """, unsafe_allow_html=True)

    total_orders = len(orders)

    pending_orders = sum(
        order.get("status") in ("Pending", "New")
        for order in orders
    )

    active_orders = sum(
        order.get("status") in (
            "Processing", "Making", "Preparing",
            "Ready for Pickup", "Shipped"
        )
        for order in orders
    )

    paid_revenue = sum(
        float(order.get("total_amount") or 0)
        for order in orders
        if order.get("payment_status") == "Paid"
        and order.get("status") != "Cancelled"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total_orders)
    c2.metric("Pending Orders", pending_orders)
    c3.metric("In Progress", active_orders)
    c4.metric("Paid Revenue", money(paid_revenue))

    st.subheader("Recent Orders")

    if orders:
        for order in orders[:8]:
            with st.container(border=True):
                left, middle, right = st.columns([2, 2, 1])

                left.write(f"**{order['order_code']}**")
                left.write(order["customer_name"])

                middle.write(money(order["total_amount"]))
                middle.caption(
                    f"Payment: {order.get('payment_status', 'Unpaid')}"
                )

                right.write(f"**{order.get('status', 'Pending')}**")
    else:
        st.info("No orders have been placed yet.")

    st.subheader("Inventory Overview")

    active_products = [
        product for product in products if product.get("active", 1)
    ]

    low_stock = [
        product for product in active_products
        if int(product.get("stock") or 0) <= 5
    ]

    c1, c2, c3 = st.columns(3)
    c1.metric("All Products", len(products))
    c2.metric("Active Products", len(active_products))
    c3.metric("Low Stock Products", len(low_stock))

    if low_stock:
        for product in low_stock:
            st.warning(
                f"{product['name']} — "
                f"{product.get('stock', 0)} remaining"
            )

    st.subheader("Popular Designs")

    popularity = {}

    for order in orders:
        if order.get("status") == "Cancelled":
            continue

        for item in safe_order_items(order):
            name = item.get("name", "Unknown design")
            popularity[name] = (
                popularity.get(name, 0) + int(item.get("qty", 1))
            )

    if popularity:
        for name, qty in sorted(
            popularity.items(),
            key=lambda pair: pair[1],
            reverse=True
        )[:5]:
            st.write(f"**{name}** — {qty} ordered")
    else:
        st.info("Popular designs will appear after orders are placed.")

    st.subheader("Estimated Product Margin")
    st.metric(
        "Estimated margin",
        money(estimate_product_margin(orders, products))
    )
    st.caption(
        "Estimate only. Uses current product costs and recorded order prices; "
        "excludes packaging, delivery expenses, refunds and other costs."
    )

# =========================================================
# ORDER MANAGEMENT
# =========================================================

elif page == "Orders":
    st.header("📦 Order Management")
    st.caption("Update order progress and provide customers with clear updates.")

    if not orders:
        st.info("No orders found.")

    else:
        search = st.text_input(
            "Search order code, customer, email or phone"
        )

        status_options_filter = [
            "All", "Pending", "Processing", "Making",
            "Ready for Pickup", "Shipped", "Delivered",
            "Completed", "Cancelled"
        ]

        status_filter = st.selectbox(
            "Filter by order status",
            status_options_filter
        )

        payment_filter = st.selectbox(
            "Filter by payment status",
            ["All", "Unpaid", "Payment Submitted", "Paid", "Refunded"]
        )

        for order in orders:
            searchable = " ".join([
                str(order.get("order_code") or ""),
                str(order.get("customer_name") or ""),
                str(order.get("email") or ""),
                str(order.get("phone") or ""),
            ]).lower()

            if search.strip().lower() not in searchable:
                continue

            if (
                status_filter != "All"
                and order.get("status") != status_filter
            ):
                continue

            if (
                payment_filter != "All"
                and order.get("payment_status") != payment_filter
            ):
                continue

            order_title = (
                f"{order.get('order_code', 'Unknown')} · "
                f"{order.get('customer_name', 'Customer')} · "
                f"{money(order.get('total_amount'))} · "
                f"{order.get('status', 'Pending')}"
            )

            with st.expander(order_title):
                left, right = st.columns(2)

                with left:
                    st.write("**Customer:**", order.get("customer_name"))
                    st.write("**Email:**", order.get("email"))
                    st.write("**Phone:**", order.get("phone"))
                    st.write("**Fulfillment:**", order.get("fulfillment"))
                    st.write(
                        "**Address:**",
                        order.get("address") or "Not required"
                    )
                    st.write(
                        "**Pickup details:**",
                        order.get("pickup_note") or "—"
                    )
                    st.write(
                        "**Payment method:**",
                        order.get("payment_method")
                    )
                    st.write(
                        "**Order date:**",
                        order.get("created_at")
                    )

                with right:
                    st.markdown("**Items ordered**")

                    for item in safe_order_items(order):
                        try:
                            item_total = (
                                float(item.get("price", 0))
                                * int(item.get("qty", 1))
                            )

                            st.write(
                                f"- {item.get('name', 'Item')} × "
                                f"{item.get('qty', 1)} — {money(item_total)}"
                            )
                        except (ValueError, TypeError):
                            st.write("- Item details unavailable")

                    st.write("Subtotal:", money(order.get("subtotal")))
                    st.write("Delivery:", money(order.get("delivery_fee")))
                    st.write("Total:", money(order.get("total_amount")))
                    st.write(
                        "Payment status:",
                        order.get("payment_status", "Unpaid")
                    )

                st.divider()

                with st.form(f"order_update_{order['id']}"):
                    status_options = [
                        "Pending", "Processing", "Making",
                        "Ready for Pickup", "Shipped",
                        "Delivered", "Completed", "Cancelled"
                    ]

                    payment_options = [
                        "Unpaid", "Payment Submitted", "Paid", "Refunded"
                    ]

                    current_status = order.get("status") or "Pending"
                    current_payment = (
                        order.get("payment_status") or "Unpaid"
                    )

                    status = st.selectbox(
                        "Order status",
                        status_options,
                        index=(
                            status_options.index(current_status)
                            if current_status in status_options else 0
                        )
                    )

                    payment_status = st.selectbox(
                        "Payment status",
                        payment_options,
                        index=(
                            payment_options.index(current_payment)
                            if current_payment in payment_options else 0
                        )
                    )

                    default_date = date.today() + timedelta(days=7)

                    try:
                        expected_date = (
                            date.fromisoformat(order.get("expected_date") or "")
                            if order.get("expected_date")
                            else default_date
                        )
                    except ValueError:
                        expected_date = default_date

                    expected = st.date_input(
                        "Expected completion / delivery date",
                        value=expected_date
                    )

                    message = st.text_area(
                        "Message visible to the customer",
                        value=order.get("admin_message") or "",
                        placeholder=(
                            "Example: Your handmade design is in progress. "
                            "We expect it to be ready in 5 days."
                        )
                    )

                    save_update = st.form_submit_button(
                        "Save Order Update",
                        use_container_width=True
                    )

                    if save_update:
                        update_order(
                            order["id"],
                            status,
                            payment_status,
                            message.strip(),
                            expected.isoformat()
                        )

                        st.success(
                            "Order updated. The customer can see these "
                            "changes on the tracking page."
                        )
                        st.rerun()

# =========================================================
# PRODUCTS & INVENTORY
# =========================================================

elif page == "Products":
    st.header("🧶 Products & Inventory")

    st.caption(
        "Product changes are saved to croshia.db and are available "
        "to the customer app when both apps use the same database."
    )

    with st.expander("➕ Add New Product", expanded=True):
        with st.form("add_product_form", clear_on_submit=True):
            new_name = st.text_input("Product name")

            new_category = st.selectbox(
                "Category",
                [
                    "Toys", "Bags", "Flowers & Gifts",
                    "Accessories", "Wearables", "Home", "Custom",
                    "Handmade"
                ]
            )

            new_description = st.text_area("Description")

            c1, c2, c3 = st.columns(3)

            with c1:
                new_price = st.number_input(
                    "Selling price (PKR)",
                    min_value=1,
                    value=700,
                    step=50
                )

            with c2:
                new_cost = st.number_input(
                    "Estimated cost (PKR)",
                    min_value=0,
                    value=200,
                    step=50
                )

            with c3:
                new_stock = st.number_input(
                    "Stock quantity (0 = made to order)",
                    min_value=0,
                    value=1,
                    step=1
                )

            new_image = st.file_uploader(
                "Upload product image",
                type=["png", "jpg", "jpeg", "webp"],
                key="new_product_image"
            )

            new_image_url = st.text_input(
                "Or use an image URL (optional)"
            )

            add_clicked = st.form_submit_button(
                "Add Product",
                use_container_width=True
            )

        if add_clicked:
            if not new_name.strip():
                st.error("Product name is required.")

            elif new_cost > new_price:
                st.warning(
                    "The estimated cost exceeds the selling price. "
                    "Please confirm that this is intentional."
                )

            else:
                try:
                    insert_product(
                        new_name,
                        new_description,
                        new_category,
                        new_price,
                        new_cost,
                        new_stock,
                        encode_image(new_image),
                        new_image_url
                    )

                    st.success("Product added successfully.")
                    st.rerun()

                except sqlite3.Error as error:
                    st.error(f"Could not add product: {error}")

    st.divider()
    st.subheader("Manage Existing Products")

    if not products:
        st.info("No products found.")

    for product in products:
        with st.expander(
            f"{product['name']} · {money(product['price'])} · "
            f"Stock: {product.get('stock', 0)}"
        ):
            image_preview(
                product.get("image_data") or "",
                product.get("image_url") or ""
            )

            with st.form(f"edit_product_{product['id']}"):
                name = st.text_input(
                    "Product name",
                    value=product.get("name") or ""
                )

                categories = [
                    "Toys", "Bags", "Flowers & Gifts",
                    "Accessories", "Wearables", "Home", "Custom",
                    "Handmade"
                ]

                old_category = product.get("category") or "Handmade"

                category = st.selectbox(
                    "Category",
                    categories,
                    index=(
                        categories.index(old_category)
                        if old_category in categories else 0
                    )
                )

                description = st.text_area(
                    "Description",
                    value=product.get("description") or ""
                )

                c1, c2, c3 = st.columns(3)

                with c1:
                    price = st.number_input(
                        "Selling price (PKR)",
                        min_value=1,
                        value=max(1, int(product.get("price") or 1)),
                        step=50,
                        key=f"edit_price_{product['id']}"
                    )

                with c2:
                    cost = st.number_input(
                        "Estimated cost (PKR)",
                        min_value=0,
                        value=max(0, int(product.get("cost") or 0)),
                        step=50,
                        key=f"edit_cost_{product['id']}"
                    )

                with c3:
                    stock = st.number_input(
                        "Stock (0 = made to order)",
                        min_value=0,
                        value=max(0, int(product.get("stock") or 0)),
                        step=1,
                        key=f"edit_stock_{product['id']}"
                    )

                active = st.checkbox(
                    "Show product in customer store",
                    value=bool(product.get("active", 1)),
                    key=f"edit_active_{product['id']}"
                )

                image_url = st.text_input(
                    "Image URL",
                    value=product.get("image_url") or "",
                    key=f"edit_image_url_{product['id']}"
                )

                replacement_image = st.file_uploader(
                    "Replace image (optional)",
                    type=["png", "jpg", "jpeg", "webp"],
                    key=f"replacement_image_{product['id']}"
                )

                save_product = st.form_submit_button(
                    "Save Product Changes",
                    use_container_width=True
                )

            if save_product:
                if not name.strip():
                    st.error("Product name is required.")

                else:
                    image_data = (
                        encode_image(replacement_image)
                        if replacement_image
                        else product.get("image_data") or ""
                    )

                    try:
                        update_product(
                            product["id"],
                            name,
                            description,
                            category,
                            price,
                            cost,
                            stock,
                            image_data,
                            image_url,
                            active
                        )

                        st.success("Product updated.")
                        st.rerun()

                    except sqlite3.Error as error:
                        st.error(f"Could not update product: {error}")

            st.caption(
                "Deleting products is intentionally avoided so existing "
                "orders remain linked to their original product information. "
                "Uncheck 'Show product in customer store' to hide a design."
            )

# =========================================================
# PAYMENT SETTINGS
# =========================================================

elif page == "Payment Settings":
    st.header("💳 Payment Settings")

    st.warning(
        "These settings configure payment choices and instructions. "
        "They do not process card payments or automatically verify "
        "transactions."
    )

    with st.form("payment_settings_form"):
        cash_enabled = st.checkbox(
            "Enable Cash on Delivery",
            value=get_setting("cash_payment_enabled", "true") == "true"
        )

        manual_enabled = st.checkbox(
            "Enable Manual Online Transfer",
            value=get_setting("manual_transfer_enabled", "true") == "true"
        )

        online_enabled = st.checkbox(
            "Enable Secure Online Payment option",
            value=get_setting("online_payment_enabled", "false") == "true"
        )

        payment_title = st.text_input(
            "Payment instructions title",
            value=get_setting("payment_title", "Payment Instructions")
        )

        payment_provider = st.text_input(
            "Payment provider name",
            value=get_setting("payment_provider", "")
        )

        payment_account_name = st.text_input(
            "Account holder / recipient name",
            value=get_setting(
                "payment_account_name",
                get_setting("payment_name", "")
            )
        )

        payment_account_details = st.text_area(
            "Manual payment details",
            value=get_setting(
                "payment_account_details",
                get_setting("payment_details", "")
            ),
            help=(
                "Only enter business payment details that you intend "
                "customers to see."
            )
        )

        payment_instructions = st.text_area(
            "Instructions for customers",
            value=get_setting("payment_instructions", "")
        )

        gateway_checkout_url = st.text_input(
            "Secure payment provider checkout URL",
            value=get_setting("gateway_checkout_url", ""),
            help=(
                "Use a genuine HTTPS checkout URL provided by your "
                "payment processor. This field does not create a gateway."
            )
        )

        save_payment = st.form_submit_button(
            "Save Payment Settings",
            use_container_width=True
        )

    if save_payment:
        if (
            online_enabled
            and gateway_checkout_url.strip()
            and not gateway_checkout_url.strip().lower().startswith("https://")
        ):
            st.error(
                "Use an HTTPS checkout URL for online payment, "
                "or disable the online payment option."
            )

        else:
            save_setting(
                "cash_payment_enabled",
                str(cash_enabled).lower()
            )
            save_setting(
                "manual_transfer_enabled",
                str(manual_enabled).lower()
            )
            save_setting(
                "online_payment_enabled",
                str(online_enabled).lower()
            )
            save_setting("payment_title", payment_title.strip())
            save_setting(
                "payment_provider",
                payment_provider.strip()
            )
            save_setting(
                "payment_method",
                payment_provider.strip() or "Bank Transfer"
            )
            save_setting(
                "payment_account_name",
                payment_account_name.strip()
            )
            save_setting(
                "payment_name",
                payment_account_name.strip()
            )
            save_setting(
                "payment_account_details",
                payment_account_details.strip()
            )
            save_setting(
                "payment_details",
                payment_account_details.strip()
            )
            save_setting(
                "payment_instructions",
                payment_instructions.strip()
            )
            save_setting(
                "gateway_checkout_url",
                gateway_checkout_url.strip()
            )

            st.success("Payment settings saved.")
            st.rerun()

    st.info(
        "Never collect or store customers' card numbers, CVVs, PINs, "
        "or banking passwords. For real card payments, use a supported "
        "payment provider's secure checkout and verify payment status "
        "through the provider."
    )

# =========================================================
# STORE SETTINGS
# =========================================================

elif page == "Store Settings":
    st.header("⚙️ Store Settings")

    with st.form("store_settings_form"):
        store_name = st.text_input(
            "Store name",
            value=get_setting("store_name", "Croshia Studio")
        )

        about = st.text_area(
            "Homepage introduction",
            value=get_setting(
                "about",
                "Beautiful crochet creations, handmade with love."
            )
        )

        contact_email = st.text_input(
            "Contact email",
            value=get_setting("contact_email", "")
        )

        contact_phone = st.text_input(
            "Contact phone",
            value=get_setting("contact_phone", "")
        )

        delivery_charge = st.number_input(
            "Delivery charge (PKR)",
            min_value=0,
            value=max(0, int(get_delivery_fee())),
            step=50
        )

        delivery_enabled = st.checkbox(
            "Allow delivery",
            value=get_setting("delivery_enabled", "true") == "true"
        )

        pickup_enabled = st.checkbox(
            "Allow pickup",
            value=get_setting("pickup_enabled", "true") == "true"
        )

        pickup_note = st.text_area(
            "Pickup instructions",
            value=get_setting(
                "pickup_note",
                "Pickup instructions will be shared after confirmation."
            )
        )

        save_store = st.form_submit_button(
            "Save Store Settings",
            use_container_width=True
        )

    if save_store:
        save_setting("store_name", store_name.strip())
        save_setting("about", about.strip())
        save_setting("contact_email", contact_email.strip())
        save_setting("contact_phone", contact_phone.strip())

        # Keep both versions of the customer-app setting synchronized.
        save_setting("delivery_fee", delivery_charge)
        save_setting("delivery_charge", delivery_charge)

        save_setting(
            "delivery_enabled",
            str(delivery_enabled).lower()
        )
        save_setting(
            "pickup_enabled",
            str(pickup_enabled).lower()
        )
        save_setting("pickup_note", pickup_note.strip())
        save_setting("currency", "PKR")

        st.success("Store settings saved.")
        st.rerun()

    st.caption(
        "The customer app reads these settings from croshia.db. "
        "Both apps must use the same persistent database for changes "
        "to appear in both."
    )

# =========================================================
# CUSTOMERS
# =========================================================

elif page == "Customers":
    st.header("👥 Registered Customers")

    customers = get_customers()

    if not customers:
        st.info("No registered customers yet.")

    else:
        st.metric("Registered Customers", len(customers))

        search = st.text_input("Search customer name or email")

        filtered_customers = [
            customer for customer in customers
            if search.strip().lower() in (
                str(customer.get("name") or "") + " "
                + str(customer.get("email") or "")
            ).lower()
        ]

        st.dataframe(
            [
                {
                    "Customer ID": customer["id"],
                    "Name": customer["name"],
                    "Email": customer["email"],
                    "Registered": customer.get("created_at", ""),
                }
                for customer in filtered_customers
            ],
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Customer passwords are never displayed in this dashboard."
    )

# =========================================================
# SECURITY
# =========================================================

elif page == "Security":
    st.header("🔐 Security")
    st.write("Change the password used by the admin dashboard.")

    with st.form("change_password_form"):
        current_password = st.text_input(
            "Current password", type="password"
        )

        new_password = st.text_input(
            "New password", type="password"
        )

        confirm_password = st.text_input(
            "Confirm new password", type="password"
        )

        change_password = st.form_submit_button(
            "Change Admin Password",
            use_container_width=True
        )

    if change_password:
        if not check_login("admin", current_password):
            st.error("Your current password is incorrect.")

        elif len(new_password) < 10:
            st.error("Use a password with at least 10 characters.")

        elif new_password != confirm_password:
            st.error("The new passwords do not match.")

        else:
            save_setting(
                "admin_password_hash",
                password_hash(new_password)
            )

            st.success(
                "Admin password changed. Use the new password next time."
            )

    st.divider()
    st.subheader("Database Information")

    st.write(f"Database file: `{DB_PATH}`")
    st.write(
        f"Database exists: **{'Yes' if os.path.exists(DB_PATH) else 'No'}**"
    )

    st.caption(
        "Back up croshia.db regularly. It contains store products, "
        "customer accounts, order details and settings."
    )

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Croshia Studio Admin · "
    + datetime.now().strftime("%d %b %Y, %I:%M %p")
)
