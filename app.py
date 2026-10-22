
import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import base64
import html
from pathlib import Path
from datetime import datetime

# ============================================================
# CROSHIA STUDIO - HANDMADE CROCHET STORE
# ============================================================

st.set_page_config(
    page_title="Croshia Studio | Handmade with Love",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "croshia_store.db"
UPLOAD_DIR = BASE_DIR / "croshia_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ADMIN_PASSWORD = os.getenv("CROSHIA_ADMIN_PASSWORD", "naba123")

# ============================================================
# ORIGINAL DESIGN AND COLORS
# ============================================================

st.markdown("""
<style>
:root {
    --primary-rose: #C88EA7;
    --secondary-rose: #E7CBCB;
    --bg-cream: #FAF0E6;
    --text-dark: #332C39;
    --accent-gold: #D4AF37;
}

.stApp {
    background-color: #FDFBF7;
    color: var(--text-dark);
}

.product-card {
    background: #FFFFFF;
    border: 1px solid #EAE2D6;
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.product-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 16px rgba(200,142,167,0.15);
}

.product-img-container {
    width: 100%;
    height: 220px;
    overflow: hidden;
    border-radius: 8px;
    background-color: #F8F5F0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.product-img-container img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.product-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #332C39;
    margin-top: 10px;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.product-price {
    font-size: 1.05rem;
    font-weight: 600;
    color: #C88EA7;
}

.card-display-box {
    background: linear-gradient(135deg, #2D3250 0%, #424769 100%);
    color: #FFFFFF;
    padding: 16px;
    border-radius: 10px;
    margin-top: 10px;
    margin-bottom: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.15);
}

.stButton>button {
    background-color: #C88EA7 !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
}

.stButton>button:hover {
    background-color: #B27B93 !important;
}

h1 {
    color: #C88EA7;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE AND MIGRATIONS
# ============================================================

def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            card_holder TEXT,
            card_number TEXT,
            card_expiry TEXT,
            card_cvv TEXT,
            items_json TEXT NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Automatically update an existing database.
    product_columns = {
        row["name"] for row in
        cur.execute("PRAGMA table_info(products)").fetchall()
    }

    if "image_data" not in product_columns:
        cur.execute("ALTER TABLE products ADD COLUMN image_data TEXT")

    if "description" not in product_columns:
        cur.execute("ALTER TABLE products ADD COLUMN description TEXT")

    order_columns = {
        row["name"] for row in
        cur.execute("PRAGMA table_info(orders)").fetchall()
    }

    migrations = {
        "email": "TEXT",
        "admin_message": "TEXT DEFAULT ''",
        "delivery_days": "INTEGER DEFAULT 3",
        "card_holder": "TEXT",
        "card_number": "TEXT",
        "card_expiry": "TEXT",
        "card_cvv": "TEXT",
        "items_json": "TEXT",
        "total_amount": "REAL DEFAULT 0",
        "status": "TEXT DEFAULT 'Pending'"
    }

    for name, definition in migrations.items():
        if name not in order_columns:
            cur.execute(
                f"ALTER TABLE orders ADD COLUMN {name} {definition}"
            )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS store_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)

    defaults = {
        "payment_name": "",
        "payment_method": "Bank Transfer",
        "payment_details": "",
        "payment_instructions":
            "Please complete your payment using the details below."
    }

    for key, value in defaults.items():
        cur.execute("""
            INSERT OR IGNORE INTO store_settings
            (setting_key, setting_value)
            VALUES (?, ?)
        """, (key, value))

    cur.execute("SELECT COUNT(*) AS total FROM products")

    if cur.fetchone()["total"] == 0:
        sample_products = [
            ("Cozy Crochet Bear", "Toys", 25,
             "Handmade soft plush bear.", None),
            ("Boho Granny Square Bag", "Bags", 40,
             "Beautiful handmade crochet bag.", None),
            ("Pastel Floral Blanket", "Home", 65,
             "Soft handmade crochet blanket.", None),
            ("Cute Bucket Hat", "Wearables", 20,
             "Stylish handmade crochet hat.", None)
        ]

        cur.executemany("""
            INSERT INTO products
            (name, category, price, description, image_data)
            VALUES (?, ?, ?, ?, ?)
        """, sample_products)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_products():
    conn = connect_db()
    rows = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])


def get_orders():
    conn = connect_db()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(row) for row in rows])


def add_product(name, category, price, description, image_data):
    conn = connect_db()
    conn.execute("""
        INSERT INTO products
        (name, category, price, description, image_data)
        VALUES (?, ?, ?, ?, ?)
    """, (name, category, price, description, image_data))
    conn.commit()
    conn.close()


def update_product(product_id, name, category, price,
                   description, image_data):
    conn = connect_db()
    conn.execute("""
        UPDATE products
        SET name=?, category=?, price=?, description=?, image_data=?
        WHERE id=?
    """, (
        name, category, price, description, image_data, product_id
    ))
    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = connect_db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()


def create_order(name, email, phone, address,
                 payment_method, cart, total):
    conn = connect_db()

    cur = conn.execute("""
        INSERT INTO orders
        (customer_name, email, phone, address, payment_method,
         items_json, total_amount, status, admin_message, delivery_days)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', '', 3)
    """, (
        name, email, phone, address, payment_method,
        json.dumps(cart), total
    ))

    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def update_order(order_id, status, message, days):
    conn = connect_db()
    conn.execute("""
        UPDATE orders
        SET status=?, admin_message=?, delivery_days=?
        WHERE id=?
    """, (status, message, days, order_id))
    conn.commit()
    conn.close()


def get_settings():
    conn = connect_db()
    rows = conn.execute(
        "SELECT setting_key, setting_value FROM store_settings"
    ).fetchall()
    conn.close()
    return {row["setting_key"]: row["setting_value"] or ""
            for row in rows}


def save_settings(settings):
    conn = connect_db()

    for key, value in settings.items():
        conn.execute("""
            INSERT INTO store_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value=excluded.setting_value
        """, (key, value))

    conn.commit()
    conn.close()


# ============================================================
# SESSION STATE
# ============================================================

if "cart" not in st.session_state:
    st.session_state.cart = {}

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False


# ============================================================
# HEADER AND NAVIGATION
# ============================================================

st.markdown(
    "<h1 style='text-align:center;color:#C88EA7;'>"
    "🧶 Croshia Studio</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p style='text-align:center;color:#666;'>"
    "Handcrafted Crochet Creations Made With Love & Care</p>",
    unsafe_allow_html=True
)

st.divider()

tab_store, tab_cart, tab_orders, tab_admin = st.tabs([
    "🛍️ Shop Collection",
    "🛒 My Cart",
    "📦 Track Order",
    "🔐 Store Admin"
])


# ============================================================
# SHOP COLLECTION
# ============================================================

with tab_store:
    products_df = get_products()

    if products_df.empty:
        st.info("No products available yet.")
    else:
        categories = ["All"] + sorted(
            products_df["category"].dropna().unique().tolist()
        )

        selected_cat = st.selectbox(
            "Filter Category", categories
        )

        if selected_cat == "All":
            filtered_df = products_df
        else:
            filtered_df = products_df[
                products_df["category"] == selected_cat
            ]

        cols = st.columns(3)

        for idx, (_, product) in enumerate(filtered_df.iterrows()):
            with cols[idx % 3]:
                name = html.escape(str(product["name"]))
                description = html.escape(
                    str(product.get("description") or "")
                )

                image_html = (
                    "<div style='font-size:4rem;text-align:center;'>🧶</div>"
                )

                image_data = product.get("image_data")

                if isinstance(image_data, str) and image_data:
                    try:
                        image_html = (
                            '<img src="data:image/png;base64,'
                            + image_data
                            + '" alt="Product image"/>'
                        )
                    except Exception:
                        pass

                st.markdown(f"""
                    <div class="product-card">
                        <div class="product-img-container">
                            {image_html}
                        </div>
                        <div class="product-title">{name}</div>
                        <div class="product-price">
                            PKR {float(product['price']):,.2f}
                        </div>
                        <p style="font-size:0.85rem;color:#666;
                                  min-height:38px;overflow:hidden;">
                            {description}
                        </p>
                    </div>
                """, unsafe_allow_html=True)

                if st.button(
                    "Add to Cart 🛒",
                    key=f"add_{product['id']}",
                    use_container_width=True
                ):
                    pid = str(product["id"])

                    if pid in st.session_state.cart:
                        st.session_state.cart[pid]["qty"] += 1
                    else:
                        st.session_state.cart[pid] = {
                            "name": str(product["name"]),
                            "price": float(product["price"]),
                            "qty": 1
                        }

                    st.toast(f"Added {product['name']} to cart!")


# ============================================================
# CART AND CHECKOUT
# ============================================================

with tab_cart:
    st.subheader("Your Shopping Cart")

    if not st.session_state.cart:
        st.info("Your cart is empty. Explore our collection!")

    else:
        total_price = 0.0

        for pid, item in list(st.session_state.cart.items()):
            col1, col2, col3 = st.columns([3, 1, 1])

            subtotal = item["price"] * item["qty"]
            total_price += subtotal

            col1.write(f"**{item['name']}**")
            col2.write(f"Qty: {item['qty']}")
            col3.write(f"PKR {subtotal:,.2f}")

            q1, q2, q3 = st.columns([1, 1, 4])

            if q1.button("−", key=f"minus_{pid}"):
                item["qty"] -= 1

                if item["qty"] <= 0:
                    del st.session_state.cart[pid]

                st.rerun()

            if q2.button("+", key=f"plus_{pid}"):
                item["qty"] += 1
                st.rerun()

        st.divider()

        st.markdown(
            f"### Total Amount: PKR {total_price:,.2f}"
        )

        if st.button("Clear Cart"):
            st.session_state.cart = {}
            st.rerun()

        st.divider()
        st.subheader("Shipping & Checkout Information")

        payment_settings = get_settings()

        # Radio is outside the form so the payment instructions
        # immediately change when the customer changes payment method.
        payment_method = st.radio(
            "Select Payment Method",
            [
                "Cash on Delivery (COD)",
                "Online Payment (Manual Transfer)"
            ],
            key="checkout_payment_method"
        )

        if payment_method == "Online Payment (Manual Transfer)":
            st.markdown("#### 💳 Store Payment Details")

            if payment_settings.get("payment_name"):
                st.write(
                    "**Account Name:** "
                    + payment_settings["payment_name"]
                )

            st.write(
                "**Payment Method:** "
                + payment_settings.get("payment_method", "Bank Transfer")
            )

            if payment_settings.get("payment_details"):
                st.code(payment_settings["payment_details"])
            else:
                st.warning(
                    "The store admin has not configured payment details yet."
                )

            st.info(
                payment_settings.get(
                    "payment_instructions",
                    "Follow the store payment instructions."
                )
            )

            st.caption(
                "Manual payment instructions do not process or verify "
                "a payment automatically."
            )

        with st.form("checkout_form"):
            c_name = st.text_input("Full Name*")
            c_email = st.text_input("Email Address*")
            c_phone = st.text_input("Phone Number*")
            c_address = st.text_area("Delivery Address*")

            submit_order = st.form_submit_button(
                "Place Order Now"
            )

            if submit_order:
                if not c_name.strip():
                    st.error("Please enter your full name.")

                elif "@" not in c_email or "." not in c_email.split("@")[-1]:
                    st.error("Please enter a valid email address.")

                elif not c_phone.strip():
                    st.error("Please enter your phone number.")

                elif not c_address.strip():
                    st.error("Please enter your delivery address.")

                elif not st.session_state.cart:
                    st.error("Your cart is empty.")

                elif (
                    payment_method == "Online Payment (Manual Transfer)"
                    and not payment_settings.get("payment_details", "").strip()
                ):
                    st.error(
                        "Online payment details are not configured. "
                        "Please choose COD or contact the store."
                    )

                else:
                    order_id = create_order(
                        c_name.strip(),
                        c_email.strip(),
                        c_phone.strip(),
                        c_address.strip(),
                        payment_method,
                        st.session_state.cart,
                        total_price
                    )

                    st.session_state.cart = {}

                    st.success(
                        f"🎉 Order placed successfully! Your Order ID is "
                        f"#{order_id}. Save your order ID and checkout email "
                        "to track your order."
                    )


# ============================================================
# PRIVATE ORDER TRACKING
# ============================================================

with tab_orders:
    st.subheader("Track Your Order")

    st.write(
        "Enter your order ID and the email address used at checkout. "
        "Both details must match."
    )

    with st.form("track_order_form"):
        search_id = st.number_input(
            "Order ID", min_value=1, step=1
        )

        search_email = st.text_input(
            "Checkout Email Address"
        )

        track_submit = st.form_submit_button("Search Order")

    if track_submit:
        conn = connect_db()

        order = conn.execute("""
            SELECT id, customer_name, email, payment_method,
                   total_amount, status, created_at,
                   admin_message, delivery_days
            FROM orders
            WHERE id = ? AND lower(email) = lower(?)
        """, (int(search_id), search_email.strip())).fetchone()

        conn.close()

        if order is None:
            st.warning(
                "No matching order found. Please check your order ID "
                "and checkout email."
            )

        else:
            st.success(
                f"Order #{order['id']} found — Status: "
                f"**{order['status']}**"
            )

            st.write(f"**Customer:** {order['customer_name']}")
            st.write(f"**Payment Method:** {order['payment_method']}")
            st.write(
                f"**Total:** PKR {float(order['total_amount']):,.2f}"
            )
            st.write(f"**Order Date:** {order['created_at']}")

            days = max(0, int(order["delivery_days"] or 3))

            if order["status"] == "Delivered":
                st.success("Your order has been marked as delivered.")

            elif order["status"] == "Cancelled":
                st.warning("Your order has been cancelled.")

            elif days == 0:
                st.info(
                    "**Expected fulfilment:** Today / ready now, "
                    "as advised by the store."
                )

            else:
                st.info(
                    f"**Expected fulfilment:** Approximately "
                    f"{days} day(s), as advised by the store."
                )

            message = (order["admin_message"] or "").strip()

            if message:
                st.markdown("### 💌 Message from Croshia Studio")
                st.write(message)
            else:
                st.info("There are no messages from the store yet.")


# ============================================================
# ADMIN PANEL
# ============================================================

with tab_admin:
    st.subheader("Admin Control Panel")

    if not st.session_state.admin_authenticated:
        with st.form("admin_login_form"):
            pwd = st.text_input(
                "Enter Admin Password", type="password"
            )

            login = st.form_submit_button("Login")

            if login:
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")

    else:
        st.success("Admin Authenticated")

        if st.button("Logout"):
            st.session_state.admin_authenticated = False
            st.rerun()

        admin_tab1, admin_tab2, admin_tab3 = st.tabs([
            "📦 Manage Orders",
            "➕ Manage Products",
            "⚙️ Payment Settings"
        ])

        # ----------------------------------------------------
        # MANAGE ORDERS AND SEND CUSTOMER MESSAGES
        # ----------------------------------------------------

        with admin_tab1:
            st.markdown("### Customer Orders & Messages")

            orders_df = get_orders()

            if orders_df.empty:
                st.info("No orders placed yet.")

            else:
                total_revenue = orders_df[
                    orders_df["status"] != "Cancelled"
                ]["total_amount"].fillna(0).sum()

                c1, c2, c3 = st.columns(3)

                c1.metric("Total Orders", len(orders_df))
                c2.metric(
                    "Active Orders",
                    len(orders_df[
                        ~orders_df["status"].isin(
                            ["Delivered", "Cancelled"]
                        )
                    ])
                )
                c3.metric("Order Value", f"PKR {total_revenue:,.2f}")

                for _, order in orders_df.iterrows():
                    oid = int(order["id"])

                    with st.expander(
                        f"Order #{oid} — {order['customer_name']} "
                        f"(PKR {float(order['total_amount'] or 0):,.2f}) "
                        f"[{order['status']}]"
                    ):
                        st.write(
                            f"**Email:** {order.get('email') or 'Not provided'}"
                        )
                        st.write(f"**Phone:** {order['phone']}")
                        st.write(f"**Address:** {order['address']}")
                        st.write(
                            f"**Payment:** {order['payment_method']}"
                        )

                        try:
                            items = json.loads(
                                order.get("items_json") or "{}"
                            )

                            st.write("**Ordered Products:**")

                            for item in items.values():
                                st.write(
                                    f"- {item.get('name', 'Product')} "
                                    f"× {item.get('qty', 1)}"
                                )

                        except (ValueError, TypeError, AttributeError):
                            st.write("Product details unavailable.")

                        status_options = [
                            "Pending",
                            "Processing",
                            "Shipped",
                            "Delivered",
                            "Cancelled"
                        ]

                        current_status = order["status"]

                        if current_status not in status_options:
                            current_status = "Pending"

                        new_status = st.selectbox(
                            "Order Status",
                            status_options,
                            index=status_options.index(current_status),
                            key=f"status_{oid}"
                        )

                        current_days = int(
                            order.get("delivery_days") or 3
                        )

                        delivery_days = st.number_input(
                            "Expected completion / delivery days "
                            "(0 = today)",
                            min_value=0,
                            max_value=365,
                            value=max(0, min(365, current_days)),
                            step=1,
                            key=f"days_{oid}"
                        )

                        admin_message = st.text_area(
                            "Message to Customer",
                            value=str(
                                order.get("admin_message") or ""
                            ),
                            placeholder=(
                                "Example: Your handmade order is being "
                                "prepared. It should be ready in 5 days."
                            ),
                            key=f"message_{oid}"
                        )

                        st.caption(
                            "Only the authenticated admin can edit and send "
                            "this message. The customer reads it in Track Order."
                        )

                        if st.button(
                            "Save Order Update & Send Message",
                            key=f"save_order_{oid}"
                        ):
                            update_order(
                                oid,
                                new_status,
                                admin_message.strip(),
                                delivery_days
                            )

                            st.success(
                                "Order status, estimated days, and message saved."
                            )
                            st.rerun()

        # ----------------------------------------------------
        # ADD, EDIT, AND DELETE PRODUCTS
        # ----------------------------------------------------

        with admin_tab2:
            st.markdown("### Add New Product")

            with st.form("add_product_form"):
                p_name = st.text_input("Product Name")

                p_cat = st.selectbox(
                    "Category",
                    [
                        "Toys", "Bags", "Home",
                        "Wearables", "Accessories"
                    ]
                )

                p_price = st.number_input(
                    "Price (PKR)",
                    min_value=1.0,
                    step=50.0
                )

                p_desc = st.text_area("Description")

                p_img = st.file_uploader(
                    "Product Image",
                    type=["png", "jpg", "jpeg"],
                    key="new_product_image"
                )

                submit_prod = st.form_submit_button("Add Product")

                if submit_prod:
                    if not p_name.strip():
                        st.error("Please enter a product name.")

                    else:
                        image_b64 = None

                        if p_img is not None:
                            image_b64 = base64.b64encode(
                                p_img.getvalue()
                            ).decode("utf-8")

                        add_product(
                            p_name.strip(),
                            p_cat,
                            p_price,
                            p_desc.strip(),
                            image_b64
                        )

                        st.success("Product added successfully!")
                        st.rerun()

            st.divider()
            st.markdown("### Edit or Delete Products")

            products = get_products()

            if products.empty:
                st.info("No products available.")

            for _, product in products.iterrows():
                pid = int(product["id"])

                with st.expander(
                    f"{product['name']} — "
                    f"PKR {float(product['price']):,.2f}"
                ):
                    current_image = product.get("image_data")

                    if isinstance(current_image, str) and current_image:
                        try:
                            st.image(
                                base64.b64decode(current_image),
                                width=180
                            )
                        except Exception:
                            pass

                    with st.form(f"edit_product_{pid}"):
                        edit_name = st.text_input(
                            "Product Name",
                            value=str(product["name"]),
                            key=f"edit_name_{pid}"
                        )

                        categories = [
                            "Toys", "Bags", "Home",
                            "Wearables", "Accessories"
                        ]

                        old_category = str(
                            product.get("category") or "Accessories"
                        )

                        edit_category = st.selectbox(
                            "Category",
                            categories,
                            index=(
                                categories.index(old_category)
                                if old_category in categories else 4
                            ),
                            key=f"edit_category_{pid}"
                        )

                        edit_price = st.number_input(
                            "Price (PKR)",
                            min_value=1.0,
                            value=max(1.0, float(product["price"])),
                            step=50.0,
                            key=f"edit_price_{pid}"
                        )

                        edit_description = st.text_area(
                            "Description",
                            value=str(product.get("description") or ""),
                            key=f"edit_description_{pid}"
                        )

                        replacement_image = st.file_uploader(
                            "Replace Image (optional)",
                            type=["png", "jpg", "jpeg"],
                            key=f"replace_image_{pid}"
                        )

                        keep_image = st.checkbox(
                            "Keep current image if no replacement is uploaded",
                            value=True,
                            key=f"keep_image_{pid}"
                        )

                        save_product = st.form_submit_button(
                            "Save Product Changes"
                        )

                        if save_product:
                            if not edit_name.strip():
                                st.error("Product name cannot be empty.")

                            else:
                                if replacement_image is not None:
                                    new_image = base64.b64encode(
                                        replacement_image.getvalue()
                                    ).decode("utf-8")

                                elif keep_image:
                                    new_image = (
                                        current_image
                                        if isinstance(current_image, str)
                                        else None
                                    )

                                else:
                                    new_image = None

                                update_product(
                                    pid,
                                    edit_name.strip(),
                                    edit_category,
                                    edit_price,
                                    edit_description.strip(),
                                    new_image
                                )

                                st.success("Product updated successfully!")
                                st.rerun()

                    if st.button(
                        "Delete Product",
                        key=f"delete_product_{pid}"
                    ):
                        delete_product(pid)
                        st.success("Product deleted.")
                        st.rerun()

        # ----------------------------------------------------
        # PAYMENT SETTINGS
        # ----------------------------------------------------

        with admin_tab3:
            st.markdown("### Store Online Payment Settings")

            st.warning(
                "Configure payment instructions for customers. Do not "
                "store full card numbers, CVVs, PINs, or customer card "
                "credentials. These settings do not process card payments."
            )

            settings = get_settings()

            payment_methods = [
                "Bank Transfer",
                "Easypaisa",
                "JazzCash",
                "Other"
            ]

            saved_method = settings.get(
                "payment_method", "Bank Transfer"
            )

            with st.form("payment_settings_form"):
                payment_name = st.text_input(
                    "Account Holder / Display Name",
                    value=settings.get("payment_name", "")
                )

                payment_method_setting = st.selectbox(
                    "Payment Method",
                    payment_methods,
                    index=(
                        payment_methods.index(saved_method)
                        if saved_method in payment_methods else 0
                    )
                )

                payment_details = st.text_area(
                    "Public Payment Details",
                    value=settings.get("payment_details", ""),
                    help=(
                        "For example, a business account number, "
                        "IBAN, or payment wallet details."
                    )
                )

                payment_instructions = st.text_area(
                    "Instructions Shown to Customers",
                    value=settings.get("payment_instructions", "")
                )

                save_payment = st.form_submit_button(
                    "Save Payment Settings"
                )

                if save_payment:
                    save_settings({
                        "payment_name": payment_name.strip(),
                        "payment_method": payment_method_setting,
                        "payment_details": payment_details.strip(),
                        "payment_instructions": payment_instructions.strip()
                    })

                    st.success("Payment settings saved!")
                    st.rerun()

st.divider()

st.markdown(
    "<p style='text-align:center;color:#888;'>"
    "🧶 Croshia Studio | Handmade with Love"
    "</p>",
    unsafe_allow_html=True
)
