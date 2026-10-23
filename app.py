
import streamlit as st
import sqlite3
import json
import base64
import html
import os
import secrets
from datetime import datetime, date, timedelta


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "croshia.db"
)

DB_PATH = "croshia.db"
ADMIN_PASSWORD = os.getenv("CROSHIA_ADMIN_PASSWORD", "change-this-password")

st.set_page_config(
    page_title="Croshia Studio | Handmade with Love",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

:root {
    --rose: #BD7895;
    --rose-dark: #985B75;
    --blush: #F5E6EB;
    --cream: #FFFAF6;
    --ink: #332A31;
}

.stApp {
    background: var(--cream);
    color: var(--ink);
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Playfair Display', serif !important;
}

h1 {
    color: var(--rose-dark) !important;
}

.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
}

.stButton > button,
.stFormSubmitButton > button {
    background: var(--rose) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    min-height: 2.6rem;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background: var(--rose-dark) !important;
}

[data-testid="stMetric"] {
    background: white;
    border: 1px solid #EFDEE5;
    padding: 14px;
    border-radius: 14px;
}

.hero {
    background: linear-gradient(115deg, #F3DFE7, #FFF5ED);
    padding: 30px;
    border-radius: 20px;
    margin: 10px 0 22px;
}

.hero-kicker {
    color: #8C586F;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-size: .75rem;
    font-weight: 700;
}

.hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.35rem;
    line-height: 1.15;
    color: #493540;
    margin: 8px 0;
}

.hero-copy {
    color: #725F68;
}

.product-card {
    background: white;
    border: 1px solid #EFE2E6;
    border-radius: 16px;
    padding: 13px;
    margin-bottom: 8px;
    box-shadow: 0 5px 18px #6F46500B;
}

.product-image {
    height: 230px;
    border-radius: 11px;
    background: #F7EEF0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.product-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.product-name {
    font-weight: 700;
    font-size: 1.04rem;
    margin-top: 10px;
}

.product-description {
    color: #786E74;
    font-size: .88rem;
    min-height: 38px;
}

.product-price {
    color: var(--rose-dark);
    font-weight: 700;
    font-size: 1.05rem;
    margin: 8px 0;
}

.muted {
    color: #786E74;
    font-size: .88rem;
}

@media(max-width:650px) {
    .hero {
        padding: 20px;
    }
    .hero-title {
        font-size: 1.8rem;
    }
    .product-image {
        height: 175px;
    }
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                image_data TEXT DEFAULT '',
                stock INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
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
                items_json TEXT NOT NULL,
                subtotal REAL NOT NULL,
                delivery_fee REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                admin_message TEXT DEFAULT '',
                expected_date TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        settings = {
            "store_name": "Croshia Studio",
            "about": "Beautiful crochet creations, handmade with love.",
            "delivery_fee": "200",
            "payment_name": "Croshia Studio",
            "payment_method": "Bank Transfer",
            "payment_details": "Update these details in the admin settings.",
            "payment_instructions": "Contact the store after making your transfer.",
            "pickup_note": "Pickup instructions will be shared after confirmation."
        }

        for key, value in settings.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                (key, value)
            )

        count = con.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            samples = [
                ("Cozy Crochet Bear", "Toys", 2500, 900,
                 "A soft handmade crochet bear.", "", 8),
                ("Boho Granny Square Bag", "Bags", 4000, 1500,
                 "A beautiful crochet tote bag.", "", 5),
                ("Pastel Floral Blanket", "Home", 6500, 3000,
                 "A cosy handmade crochet blanket.", "", 3),
                ("Cute Bucket Hat", "Wearables", 2000, 700,
                 "A stylish crochet sun hat.", "", 8),
                ("Crochet Flower Bouquet", "Flowers & Gifts", 1800, 600,
                 "A handmade bouquet for a special gift.", "", 10),
                ("Crochet Keychain", "Accessories", 700, 200,
                 "A small handmade bag charm.", "", 15)
            ]

            con.executemany("""
                INSERT INTO products
                (name,category,price,cost,description,image_data,stock,created_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, [(*p, now) for p in samples])


init_db()


# ---------------- HELPERS ----------------

def money(amount):
    return f"PKR {float(amount):,.0f}"


def setting(key, default=""):
    with db() as con:
        row = con.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()
    return row["value"] if row else default


def save_setting(key, value):
    with db() as con:
        con.execute("""
            INSERT INTO settings(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))


def get_products(active_only=True):
    with db() as con:
        query = "SELECT * FROM products"
        if active_only:
            query += " WHERE active=1"
        query += " ORDER BY id DESC"
        return [dict(r) for r in con.execute(query).fetchall()]


def get_orders():
    with db() as con:
        rows = con.execute(
            "SELECT * FROM orders ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def go(page):
    st.session_state.page = page
    st.rerun()


def image_html(data):
    if data:
        return (
            '<img src="data:image/jpeg;base64,'
            + data
            + '" alt="Crochet product">'
        )
    return '<div style="font-size:4rem">🧶</div>'


# ---------------- SESSION STATE ----------------

defaults = {
    "page": "shop",
    "cart": {},
    "admin_logged_in": False,
    "last_order_code": "",
    "last_order_email": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------- HEADER ----------------

# ---------------- CUSTOMER HEADER ----------------


# ---------------- CUSTOMER HEADER ----------------

st.markdown(
    f"""
    <div style="
        padding-top: 12px;
        padding-bottom: 8px;
    ">
        <div style="
            color: #985B75;
            font-size: 1.45rem;
            font-weight: 700;
        ">
            🧶 {html.escape(setting('store_name'))}
        </div>
        <div style="color: #907D86; font-size: 0.85rem;">
            Handcrafted with love and care
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Full-width navigation with equal button widths
nav1, nav2, nav3 = st.columns(3, gap="small")

with nav1:
    if st.button("🏠 Shop", use_container_width=True):
        go("shop")

with nav2:
    quantity = sum(
        item["qty"]
        for item in st.session_state.cart.values()
    )

    if st.button(
        f"🛒 Cart ({quantity})",
        use_container_width=True
    ):
        go("cart")

with nav3:
    if st.button("📦 Track Order", use_container_width=True):
        go("track")

st.divider()


# =====================================================
# ADMIN PANEL
# =====================================================

if st.session_state.page == "admin":

    st.title("Croshia Studio — Admin Panel")
    st.write("Manage your store, orders, inventory and customer updates.")

    if not st.session_state.admin_logged_in:

        st.subheader("Admin Login")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login = st.form_submit_button("Login")

        if login:
            if (
                username.strip().lower() == "admin"
                and secrets.compare_digest(password, ADMIN_PASSWORD)
            ):
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Incorrect username or password.")

        st.info(
            "Set CROSHIA_ADMIN_PASSWORD in your deployment environment. "
            "The fallback password is for local testing only."
        )
        st.stop()

    if st.button("Log Out"):
        st.session_state.admin_logged_in = False
        go("shop")

    orders = get_orders()
    products = get_products(active_only=False)

    paid_revenue = sum(
        o["total_amount"]
        for o in orders
        if o["payment_status"] == "Paid"
        and o["status"] != "Cancelled"
    )

    pending = sum(
        o["status"] in ["Pending", "Processing", "Making"]
        for o in orders
    )

    delivered = sum(
        o["status"] == "Delivered"
        for o in orders
    )

    a, b, c, d = st.columns(4)
    a.metric("Total Orders", len(orders))
    b.metric("Pending Orders", pending)
    c.metric("Delivered Orders", delivered)
    d.metric("Paid Revenue", money(paid_revenue))

    tab_orders, tab_products, tab_settings = st.tabs([
        "📦 Orders",
        "🧶 Products & Inventory",
        "⚙️ Store Settings"
    ])

    # ---------------- ORDER MANAGEMENT ----------------

    with tab_orders:

        search = st.text_input(
            "Search order ID, customer, email or phone"
        )

        status_filter = st.selectbox(
            "Filter by order status",
            [
                "All", "Pending", "Processing", "Making",
                "Ready for Pickup", "Shipped", "Delivered",
                "Cancelled"
            ]
        )

        filtered_orders = orders

        if search.strip():
            q = search.strip().lower()
            filtered_orders = [
                o for o in filtered_orders
                if q in o["order_code"].lower()
                or q in o["customer_name"].lower()
                or q in o["email"].lower()
                or q in o["phone"].lower()
            ]

        if status_filter != "All":
            filtered_orders = [
                o for o in filtered_orders
                if o["status"] == status_filter
            ]

        if not filtered_orders:
            st.info("No matching orders.")

        for order in filtered_orders:

            title = (
                f"{order['order_code']} · "
                f"{order['customer_name']} · "
                f"{money(order['total_amount'])} · "
                f"{order['status']}"
            )

            with st.expander(title):

                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Customer:**", order["customer_name"])
                    st.write("**Email:**", order["email"])
                    st.write("**Phone:**", order["phone"])
                    st.write("**Fulfillment:**", order["fulfillment"])
                    st.write("**Address:**", order["address"] or "Not required")
                    st.write("**Pickup details:**", order["pickup_note"] or "—")
                    st.write("**Payment method:**", order["payment_method"])
                    st.write("**Order date:**", order["created_at"])

                with col2:
                    st.write("**Items ordered**")

                    try:
                        items = json.loads(order["items_json"])
                        for item in items:
                            st.write(
                                f"• {item['name']} × {item['qty']} — "
                                f"{money(item['price'] * item['qty'])}"
                            )
                    except Exception:
                        st.write("Item details unavailable.")

                    st.write("Subtotal:", money(order["subtotal"]))
                    st.write("Delivery:", money(order["delivery_fee"]))
                    st.write("Total:", money(order["total_amount"]))
                    st.write("Payment status:", order["payment_status"])

                with st.form(f"order_update_{order['id']}"):

                    statuses = [
                        "Pending", "Processing", "Making",
                        "Ready for Pickup", "Shipped",
                        "Delivered", "Cancelled"
                    ]

                    current_status = order["status"]
                    status_index = (
                        statuses.index(current_status)
                        if current_status in statuses else 0
                    )

                    new_status = st.selectbox(
                        "Order status",
                        statuses,
                        index=status_index
                    )

                    payment_statuses = [
                        "Unpaid", "Payment Submitted", "Paid", "Refunded"
                    ]

                    current_payment = order["payment_status"]
                    payment_index = (
                        payment_statuses.index(current_payment)
                        if current_payment in payment_statuses else 0
                    )

                    new_payment = st.selectbox(
                        "Payment status",
                        payment_statuses,
                        index=payment_index
                    )

                    expected = order["expected_date"]
                    try:
                        expected_value = date.fromisoformat(expected)
                    except (ValueError, TypeError):
                        expected_value = date.today() + timedelta(days=7)

                    new_expected = st.date_input(
                        "Expected completion / delivery date",
                        value=expected_value
                    )

                    new_message = st.text_area(
                        "Message visible to customer",
                        value=order["admin_message"] or ""
                    )

                    save_update = st.form_submit_button("Save Order Update")

                    if save_update:
                        with db() as con:
                            con.execute("""
                                UPDATE orders
                                SET status=?, payment_status=?,
                                    expected_date=?, admin_message=?
                                WHERE id=?
                            """, (
                                new_status,
                                new_payment,
                                new_expected.isoformat(),
                                new_message.strip(),
                                order["id"]
                            ))

                        st.success("Order updated.")
                        st.rerun()

    # ---------------- PRODUCT MANAGEMENT ----------------

    with tab_products:

        st.subheader("Add a New Product")

        with st.form("add_product_form", clear_on_submit=True):

            name = st.text_input("Product name")

            category = st.selectbox(
                "Category",
                [
                    "Toys", "Bags", "Flowers & Gifts",
                    "Accessories", "Wearables", "Home", "Custom"
                ]
            )

            price = st.number_input(
                "Selling price (PKR)",
                min_value=1,
                value=1000,
                step=100
            )

            cost = st.number_input(
                "Estimated product cost (PKR)",
                min_value=0,
                value=0,
                step=100
            )

            stock = st.number_input(
                "Stock quantity (0 = made to order)",
                min_value=0,
                value=5,
                step=1
            )

            description = st.text_area("Description")

            photo = st.file_uploader(
                "Product image",
                type=["png", "jpg", "jpeg", "webp"]
            )

            add = st.form_submit_button("Add Product")

            if add:

                if not name.strip():
                    st.error("Enter a product name.")
                else:
                    encoded = (
                        base64.b64encode(photo.getvalue()).decode("utf-8")
                        if photo else ""
                    )

                    with db() as con:
                        con.execute("""
                            INSERT INTO products
                            (name,category,price,cost,description,
                             image_data,stock,active,created_at)
                            VALUES(?,?,?,?,?,?,?,1,?)
                        """, (
                            name.strip(), category, price, cost,
                            description.strip(), encoded, stock,
                            datetime.now().strftime("%Y-%m-%d %H:%M")
                        ))

                    st.success("Product added.")
                    st.rerun()

        st.divider()
        st.subheader("Existing Products")

        for product in products:

            with st.expander(
                f"{product['name']} · {money(product['price'])} · "
                f"Stock: {product['stock']}"
            ):

                with st.form(f"edit_product_{product['id']}"):

                    new_name = st.text_input(
                        "Name", value=product["name"]
                    )

                    categories = [
                        "Toys", "Bags", "Flowers & Gifts",
                        "Accessories", "Wearables", "Home", "Custom"
                    ]

                    old_category = product["category"]
                    cat_index = (
                        categories.index(old_category)
                        if old_category in categories else 0
                    )

                    new_category = st.selectbox(
                        "Category",
                        categories,
                        index=cat_index
                    )

                    new_price = st.number_input(
                        "Selling price",
                        min_value=1,
                        value=int(product["price"]),
                        step=100
                    )

                    new_cost = st.number_input(
                        "Estimated cost",
                        min_value=0,
                        value=int(product["cost"]),
                        step=100
                    )

                    new_stock = st.number_input(
                        "Stock (0 = made to order)",
                        min_value=0,
                        value=int(product["stock"]),
                        step=1
                    )

                    new_description = st.text_area(
                        "Description",
                        value=product["description"]
                    )

                    active = st.checkbox(
                        "Show in store",
                        value=bool(product["active"])
                    )

                    new_photo = st.file_uploader(
                        "Replace image (optional)",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"image_{product['id']}"
                    )

                    update_product = st.form_submit_button("Save Product")

                    if update_product:

                        encoded = (
                            base64.b64encode(
                                new_photo.getvalue()
                            ).decode("utf-8")
                            if new_photo else product["image_data"]
                        )

                        with db() as con:
                            con.execute("""
                                UPDATE products
                                SET name=?, category=?, price=?, cost=?,
                                    stock=?, description=?, active=?,
                                    image_data=?
                                WHERE id=?
                            """, (
                                new_name.strip(),
                                new_category,
                                new_price,
                                new_cost,
                                new_stock,
                                new_description.strip(),
                                int(active),
                                encoded,
                                product["id"]
                            ))

                        st.success("Product updated.")
                        st.rerun()

                if st.button(
                    "Delete Product",
                    key=f"delete_product_{product['id']}"
                ):
                    with db() as con:
                        con.execute(
                            "DELETE FROM products WHERE id=?",
                            (product["id"],)
                        )
                    st.rerun()

    # ---------------- STORE SETTINGS ----------------

    with tab_settings:

        st.subheader("Store Settings")

        with st.form("settings_form"):

            store_name = st.text_input(
                "Store name",
                value=setting("store_name", "Croshia Studio")
            )

            about = st.text_area(
                "Homepage introduction",
                value=setting("about", "Handmade with love.")
            )

            delivery_fee = st.number_input(
                "Delivery fee (PKR)",
                min_value=0,
                value=int(float(setting("delivery_fee", "200"))),
                step=50
            )

            pickup_note = st.text_area(
                "Pickup instructions",
                value=setting("pickup_note")
            )

            payment_name = st.text_input(
                "Account display name",
                value=setting("payment_name")
            )

            methods = [
                "Bank Transfer", "Easypaisa", "JazzCash", "Other"
            ]

            current_method = setting("payment_method", "Bank Transfer")
            method_index = (
                methods.index(current_method)
                if current_method in methods else 0
            )

            payment_method = st.selectbox(
                "Manual payment method",
                methods,
                index=method_index
            )

            payment_details = st.text_area(
                "Public payment details",
                value=setting("payment_details")
            )

            payment_instructions = st.text_area(
                "Customer payment instructions",
                value=setting("payment_instructions")
            )

            save = st.form_submit_button("Save Settings")

            if save:

                values = {
                    "store_name": store_name,
                    "about": about,
                    "delivery_fee": delivery_fee,
                    "pickup_note": pickup_note,
                    "payment_name": payment_name,
                    "payment_method": payment_method,
                    "payment_details": payment_details,
                    "payment_instructions": payment_instructions
                }

                for key, value in values.items():
                    save_setting(key, value)

                st.success("Store settings saved.")

        st.divider()
        st.subheader("Popular Products")

        popularity = {}

        for order in orders:
            if order["status"] == "Cancelled":
                continue

            try:
                for item in json.loads(order["items_json"]):
                    popularity[item["name"]] = (
                        popularity.get(item["name"], 0)
                        + int(item["qty"])
                    )
            except Exception:
                pass

        if popularity:
            for name, qty in sorted(
                popularity.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                st.write(f"• {name}: {qty} unit(s)")
        else:
            st.info("No completed shopping activity yet.")

        # Estimate profit using recorded costs for currently existing products.
        product_costs = {
            p["name"]: float(p["cost"])
            for p in products
        }

        estimated_profit = 0.0

        for order in orders:
            if order["status"] == "Cancelled":
                continue

            try:
                for item in json.loads(order["items_json"]):
                    cost_per_item = product_costs.get(item["name"], 0)
                    estimated_profit += (
                        float(item["price"]) - cost_per_item
                    ) * int(item["qty"])
            except Exception:
                pass

        st.metric("Estimated product margin", money(estimated_profit))
        st.caption(
            "Estimate only: this excludes packaging, delivery expenses, "
            "refunds and other business costs. Historical costs are not "
            "saved per order in this starter version."
        )

    st.stop()


# =====================================================
# CUSTOMER SHOP
# =====================================================

if st.session_state.page == "shop":

    st.markdown(f"""
    <div class="hero">
        <div class="hero-kicker">Small stitches · Big feelings</div>
        <div class="hero-title">
            Handmade treasures,<br>made to make you smile.
        </div>
        <div class="hero-copy">
            {html.escape(setting("about"))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    products = get_products()

    categories = ["All"] + sorted(
        set(p["category"] for p in products)
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        chosen_category = st.selectbox(
            "Explore by category",
            categories
        )

    with col2:
        search = st.text_input(
            "Search creations",
            placeholder="Flowers, bags, toys..."
        )

    filtered = [
        p for p in products
        if (
            chosen_category == "All"
            or p["category"] == chosen_category
        )
        and search.lower() in (
            p["name"] + " " + p["description"] + " " + p["category"]
        ).lower()
    ]

    st.subheader("Made with care, picked by you")

    if not filtered:
        st.info("No products match your search.")

    cols = st.columns(3)

    for i, product in enumerate(filtered):

        with cols[i % 3]:

            st.markdown(f"""
            <div class="product-card">
                <div class="product-image">
                    {image_html(product['image_data'])}
                </div>
                <div class="product-name">
                    {html.escape(product['name'])}
                </div>
                <div class="product-description">
                    {html.escape(product['description'])}
                </div>
                <div class="product-price">
                    {money(product['price'])}
                </div>
                <div class="muted">
                    {html.escape(product['category'])}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "Add to Cart ＋",
                key=f"add_{product['id']}",
                use_container_width=True
            ):

                pid = str(product["id"])

                if pid in st.session_state.cart:
                    st.session_state.cart[pid]["qty"] += 1
                else:
                    st.session_state.cart[pid] = {
                        "product_id": product["id"],
                        "name": product["name"],
                        "price": float(product["price"]),
                        "qty": 1
                    }

                st.toast(f"{product['name']} added to cart.")


# =====================================================
# CART AND CHECKOUT
# =====================================================

elif st.session_state.page == "cart":

    st.title("Your Shopping Cart")

    cart = st.session_state.cart

    if not cart:
        st.info("Your cart is empty.")

        if st.button("Explore Collection"):
            go("shop")

        st.stop()

    products_by_id = {
        str(p["id"]): p for p in get_products(active_only=False)
    }

    subtotal = 0.0

    for pid, item in list(cart.items()):

        c1, c2, c3, c4 = st.columns([4, 1, 1, 1])

        with c1:
            st.write(f"**{item['name']}**")
            st.caption(f"{money(item['price'])} each")

        with c2:
            st.write(f"Qty: {item['qty']}")

        with c3:
            st.write(money(item["price"] * item["qty"]))

        with c4:
            if st.button("Remove", key=f"remove_{pid}"):
                del st.session_state.cart[pid]
                st.rerun()

        q1, q2, _ = st.columns([1, 1, 5])

        with q1:
            if st.button("−", key=f"minus_{pid}"):
                item["qty"] -= 1

                if item["qty"] <= 0:
                    del st.session_state.cart[pid]

                st.rerun()

        with q2:
            if st.button("+", key=f"plus_{pid}"):
                item["qty"] += 1
                st.rerun()

        subtotal += item["price"] * item["qty"]

    st.divider()

    st.markdown(f"### Subtotal: {money(subtotal)}")

    if st.button("Clear Cart"):
        st.session_state.cart = {}
        st.rerun()

    st.divider()
    st.subheader("Shipping and Checkout")

    with st.form("checkout_form"):

        customer_name = st.text_input("Full name *")
        email = st.text_input("Email address *")
        phone = st.text_input("Phone number *", placeholder="03001234567")

        fulfillment = st.radio(
            "How would you like to receive your order?",
            ["Delivery", "Pickup"],
            horizontal=True
        )

        address = ""

        if fulfillment == "Delivery":
            address = st.text_area("Complete delivery address *")
        else:
            st.info(setting("pickup_note"))

        pickup_note = ""

        if fulfillment == "Pickup":
            pickup_note = st.text_input(
                "Pickup name or preferred contact (optional)"
            )

        payment_method = st.radio(
            "Payment method",
            ["Cash on Delivery", "Manual Online Transfer"]
        )

        if payment_method == "Manual Online Transfer":

            st.markdown("#### Payment instructions")

            st.write("**Account:**", setting("payment_name"))
            st.write("**Method:**", setting("payment_method"))
            st.code(setting("payment_details"))
            st.info(setting("payment_instructions"))

            st.caption(
                "This is manual transfer, not card processing. "
                "Never enter card numbers, CVV, PIN or banking passwords."
            )

        place_order = st.form_submit_button("Place Order")

        if place_order:

            if not customer_name.strip():
                st.error("Please enter your full name.")

            elif (
                "@" not in email
                or "." not in email.split("@")[-1]
            ):
                st.error("Please enter a valid email address.")

            elif (
                not phone.strip()
                or not phone.replace("+", "").replace(" ", "").isdigit()
                or len(phone.replace("+", "").replace(" ", "")) < 7
            ):
                st.error("Please enter a valid phone number.")

            elif fulfillment == "Delivery" and not address.strip():
                st.error("Please enter your delivery address.")

            elif not st.session_state.cart:
                st.error("Your cart is empty.")

            else:

                unavailable = []

                for pid, item in st.session_state.cart.items():

                    product = products_by_id.get(pid)

                    if not product or not product["active"]:
                        unavailable.append(item["name"])

                    elif (
                        int(product["stock"]) > 0
                        and int(product["stock"]) < int(item["qty"])
                    ):
                        unavailable.append(item["name"])

                if unavailable:

                    st.error(
                        "Please check availability for: "
                        + ", ".join(unavailable)
                    )

                else:

                    delivery_fee = (
                        float(setting("delivery_fee", "200"))
                        if fulfillment == "Delivery"
                        else 0.0
                    )

                    total = subtotal + delivery_fee

                    order_code = (
                        "CRS-"
                        + datetime.now().strftime("%y%m%d")
                        + "-"
                        + secrets.token_hex(3).upper()
                    )

                    items = [
                        {
                            "product_id": int(item["product_id"]),
                            "name": item["name"],
                            "price": float(item["price"]),
                            "qty": int(item["qty"])
                        }
                        for pid, item in st.session_state.cart.items()
                    ]

                    created_at = datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    )

                    expected_date = (
                        date.today() + timedelta(days=7)
                    ).isoformat()

                    try:
                        with db() as con:

                            con.execute("""
                                INSERT INTO orders (
                                    order_code, customer_name, email, phone,
                                    fulfillment, address, pickup_note,
                                    payment_method, payment_status,
                                    items_json, subtotal, delivery_fee,
                                    total_amount, status, admin_message,
                                    expected_date, created_at
                                )
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (
                                order_code,
                                customer_name.strip(),
                                email.strip().lower(),
                                phone.strip(),
                                fulfillment,
                                address.strip(),
                                pickup_note.strip(),
                                payment_method,
                                "Unpaid",
                                json.dumps(items),
                                subtotal,
                                delivery_fee,
                                total,
                                "Pending",
                                "Thank you! Your order has been received. "
                                "We will confirm your order shortly.",
                                expected_date,
                                created_at
                            ))

                            for item in items:

                                row = con.execute(
                                    "SELECT stock FROM products WHERE id=?",
                                    (item["product_id"],)
                                ).fetchone()

                                # Zero stock means made-to-order.
                                if row and int(row["stock"]) > 0:
                                    con.execute("""
                                        UPDATE products
                                        SET stock=MAX(0, stock-?)
                                        WHERE id=?
                                    """, (
                                        item["qty"],
                                        item["product_id"]
                                    ))

                        # Clear cart only after the database save succeeds.
                        st.session_state.cart = {}

                        # Save lookup details for automatic tracking.
                        st.session_state.last_order_code = order_code
                        st.session_state.last_order_email = email.strip().lower()

                        # Redirect to the tracking page automatically.
                        st.session_state.page = "track"
                        st.rerun()

                    except sqlite3.Error:
                        st.error(
                            "We could not save your order. "
                            "Your cart has not been cleared. Please try again."
                        )


# =====================================================
# ORDER TRACKING
# =====================================================

elif st.session_state.page == "track":

    st.title("Track Your Order")

    st.write(
        "Enter your order ID and checkout email to see the latest status."
    )

    if st.session_state.last_order_code:
        st.success(
            f"Order placed successfully! Your ID is "
            f"**{st.session_state.last_order_code}**"
        )
        st.caption("Your cart has been cleared and your order has been saved.")

    with st.form("track_order_form"):

        order_code = st.text_input(
            "Order ID",
            value=st.session_state.last_order_code
        )

        email = st.text_input(
            "Checkout email",
            value=st.session_state.last_order_email
        )

        track = st.form_submit_button("View Order")

    if track or st.session_state.last_order_code:

        code_to_find = (
            order_code if track
            else st.session_state.last_order_code
        ).strip().upper()

        email_to_find = (
            email if track
            else st.session_state.last_order_email
        ).strip().lower()

        with db() as con:

            row = con.execute("""
                SELECT * FROM orders
                WHERE order_code=? AND lower(email)=?
            """, (code_to_find, email_to_find)).fetchone()

        if row:

            order = dict(row)

            a, b, c = st.columns(3)

            a.metric("Order Total", money(order["total_amount"]))
            b.metric("Order Status", order["status"])
            c.metric("Payment Status", order["payment_status"])

            st.write("**Order ID:**", order["order_code"])
            st.write("**Order date:**", order["created_at"])
            st.write("**Fulfillment:**", order["fulfillment"])

            if order["address"]:
                st.write("**Delivery address:**", order["address"])

            if order["expected_date"]:
                st.write(
                    "**Expected completion / delivery:**",
                    order["expected_date"]
                )

            st.subheader("Your Items")

            try:
                for item in json.loads(order["items_json"]):
                    st.write(
                        f"• {item['name']} × {item['qty']} — "
                        f"{money(item['price'] * item['qty'])}"
                    )
            except Exception:
                st.write("Item details unavailable.")

            if order["status"] == "Delivered":
                st.success("Your order has been delivered.")

            elif order["status"] == "Cancelled":
                st.warning("This order has been cancelled.")

            else:
                st.info("Your order is being processed.")

            st.subheader("Message from Croshia Studio")
            st.write(
                order["admin_message"]
                or "There are no additional updates yet."
            )

            st.caption(
                "Keep your order ID and checkout email private."
            )

        elif track:
            st.warning(
                "No matching order found. Check your order ID and email."
            )

    if st.button("Continue Shopping"):
        go("shop")


# ---------------- FOOTER ----------------

st.divider()

st.markdown("""
<div style="text-align:center;color:#907D86;font-size:.85rem">
    🧶 Croshia Studio · Handmade with love · Pakistan
</div>
""", unsafe_allow_html=True)
