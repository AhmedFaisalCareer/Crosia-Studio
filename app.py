
import streamlit as st
import sqlite3
import json
import base64
import hashlib
import hmac
import html
import os
import secrets
from datetime import datetime, date, timedelta

# ---------------- CONFIGURATION ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "croshia.db")

st.set_page_config(
    page_title="Croshia Studio | Handmade with Love",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------- STYLE ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

:root {
    --rose:#BD7895;
    --rose-dark:#985B75;
    --cream:#FFFAF6;
    --ink:#332A31;
}

.stApp {
    background:var(--cream);
    color:var(--ink);
    font-family:'DM Sans',sans-serif;
}

h1,h2,h3 {
    font-family:'Playfair Display',serif !important;
}

h1 {
    color:var(--rose-dark) !important;
}

.block-container {
    max-width:1250px;
    padding-top:1.5rem;
    padding-bottom:3rem;
}

.stButton>button,
.stFormSubmitButton>button {
    background:var(--rose)!important;
    color:white!important;
    border:none!important;
    border-radius:10px!important;
    font-weight:700!important;
    min-height:2.6rem;
}

.stButton>button:hover,
.stFormSubmitButton>button:hover {
    background:var(--rose-dark)!important;
}

[data-testid="stMetric"] {
    background:white;
    border:1px solid #EFDEE5;
    padding:14px;
    border-radius:14px;
}

.hero {
    background:linear-gradient(115deg,#F3DFE7,#FFF5ED);
    padding:30px;
    border-radius:20px;
    margin:10px 0 22px;
}

.hero-kicker {
    color:#8C586F;
    text-transform:uppercase;
    letter-spacing:2px;
    font-size:.75rem;
    font-weight:700;
}

.hero-title {
    font-family:'Playfair Display',serif;
    font-size:2.35rem;
    line-height:1.15;
    color:#493540;
    margin:8px 0;
}

.hero-copy {
    color:#725F68;
}

.product-card {
    background:white;
    border:1px solid #EFE2E6;
    border-radius:16px;
    padding:13px;
    margin-bottom:8px;
    box-shadow:0 5px 18px #6F46500B;
}

.product-image {
    height:230px;
    border-radius:11px;
    background:#F7EEF0;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow:hidden;
}

.product-image img {
    width:100%;
    height:100%;
    object-fit:cover;
}

.product-name {
    font-weight:700;
    font-size:1.04rem;
    margin-top:10px;
}

.product-description {
    color:#786E74;
    font-size:.88rem;
    min-height:38px;
}

.product-price {
    color:var(--rose-dark);
    font-weight:700;
    font-size:1.05rem;
    margin:8px 0;
}

.muted {
    color:#786E74;
    font-size:.88rem;
}

@media(max-width:650px) {
    .hero { padding:20px; }
    .hero-title { font-size:1.8rem; }
    .product-image { height:175px; }
}
</style>
""", unsafe_allow_html=True)

# ---------------- DATABASE ----------------

def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=20000")
    return con


def table_exists(con, table):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone() is not None


def get_columns(con, table):
    return {
        row["name"]
        for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def add_column(con, table, column, definition):
    if table_exists(con, table) and column not in get_columns(con, table):
        con.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'
        )


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 310000
    )
    return (
        "pbkdf2_sha256$310000$"
        + base64.b64encode(salt).decode()
        + "$"
        + base64.b64encode(digest).decode()
    )


def verify_password(password, stored):
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$", 3)

        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)

        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )

        return hmac.compare_digest(actual, expected)

    except (ValueError, TypeError):
        return False


def init_db():
    with db() as con:
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

        # Safely add compatible fields to an existing database.
        add_column(con, "products", "category", "TEXT DEFAULT 'Handmade'")
        add_column(con, "products", "cost", "REAL NOT NULL DEFAULT 0")
        add_column(con, "products", "description", "TEXT DEFAULT ''")
        add_column(con, "products", "image_data", "TEXT DEFAULT ''")
        add_column(con, "products", "image_url", "TEXT DEFAULT ''")
        add_column(con, "products", "stock", "INTEGER NOT NULL DEFAULT 0")
        add_column(con, "products", "active", "INTEGER NOT NULL DEFAULT 1")
        add_column(con, "products", "created_at", "TEXT DEFAULT ''")

        add_column(con, "orders", "order_code", "TEXT")
        add_column(con, "orders", "customer_name", "TEXT DEFAULT ''")
        add_column(con, "orders", "email", "TEXT DEFAULT ''")
        add_column(con, "orders", "phone", "TEXT DEFAULT ''")
        add_column(con, "orders", "fulfillment", "TEXT DEFAULT 'Delivery'")
        add_column(con, "orders", "address", "TEXT DEFAULT ''")
        add_column(con, "orders", "pickup_note", "TEXT DEFAULT ''")
        add_column(con, "orders", "payment_method", "TEXT DEFAULT 'Cash on Delivery'")
        add_column(con, "orders", "payment_status", "TEXT DEFAULT 'Unpaid'")
        add_column(con, "orders", "items_json", "TEXT DEFAULT '[]'")
        add_column(con, "orders", "subtotal", "REAL DEFAULT 0")
        add_column(con, "orders", "delivery_fee", "REAL DEFAULT 0")
        add_column(con, "orders", "total_amount", "REAL DEFAULT 0")
        add_column(con, "orders", "status", "TEXT DEFAULT 'Pending'")
        add_column(con, "orders", "admin_message", "TEXT DEFAULT ''")
        add_column(con, "orders", "expected_date", "TEXT DEFAULT ''")
        add_column(con, "orders", "created_at", "TEXT DEFAULT ''")

        defaults = {
            "store_name": "Croshia Studio",
            "about": "Beautiful crochet creations, handmade with love.",
            "delivery_fee": "200",
            "delivery_charge": "200",
            "delivery_enabled": "true",
            "pickup_enabled": "true",
            "currency": "PKR",
            "payment_name": "Croshia Studio",
            "payment_method": "Bank Transfer",
            "payment_details": "Contact the store for payment details.",
            "payment_instructions": "Contact the store after making your transfer.",
            "payment_title": "Payment Instructions",
            "payment_account_name": "Croshia Studio",
            "payment_account_details": "",
            "payment_provider": "",
            "gateway_checkout_url": "",
            "online_payment_enabled": "false",
            "cash_payment_enabled": "true",
            "contact_email": "",
            "contact_phone": "",
            "pickup_note": "Pickup instructions will be shared after confirmation.",
        }

        for key, value in defaults.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                (key, value)
            )

        count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]

        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            samples = [
                ("Cozy Crochet Bear", "Toys", 2500, 900,
                 "A soft handmade crochet bear.", "", "", 8),
                ("Boho Granny Square Bag", "Bags", 4000, 1500,
                 "A beautiful crochet tote bag.", "", "", 5),
                ("Pastel Floral Blanket", "Home", 6500, 3000,
                 "A cosy handmade crochet blanket.", "", "", 3),
                ("Cute Bucket Hat", "Wearables", 2000, 700,
                 "A stylish crochet sun hat.", "", "", 8),
                ("Crochet Flower Bouquet", "Flowers & Gifts", 1800, 600,
                 "A handmade bouquet for a special gift.", "", "", 10),
                ("Crochet Keychain", "Accessories", 700, 200,
                 "A small handmade bag charm.", "", "", 15),
            ]

            con.executemany("""
                INSERT INTO products(
                    name,category,price,cost,description,
                    image_data,image_url,stock,created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
            """, [(*p, now) for p in samples])


init_db()

# ---------------- HELPERS ----------------

def money(amount):
    return f"PKR {float(amount or 0):,.0f}"


def setting(key, default=""):
    aliases = {
        "delivery_fee": ("delivery_fee", "delivery_charge"),
        "payment_name": ("payment_name", "payment_account_name"),
        "payment_method": ("payment_method", "payment_provider"),
        "payment_details": ("payment_details", "payment_account_details"),
        "payment_instructions": ("payment_instructions",),
        "pickup_note": ("pickup_note",),
    }

    keys = aliases.get(key, (key,))

    with db() as con:
        for candidate in keys:
            row = con.execute(
                "SELECT value FROM settings WHERE key=?", (candidate,)
            ).fetchone()

            if row and row["value"] != "":
                return row["value"]

    return default


def get_products(active_only=True):
    with db() as con:
        query = "SELECT * FROM products"
        if active_only:
            query += " WHERE active=1"
        query += " ORDER BY id DESC"
        return [dict(row) for row in con.execute(query).fetchall()]


def get_product_image(product):
    if product.get("image_data"):
        return "data:image/jpeg;base64," + product["image_data"]

    return product.get("image_url") or ""


def email_valid(email):
    email = email.strip()
    return (
        "@" in email
        and "." in email.split("@")[-1]
        and " " not in email
    )


def signed_in():
    return st.session_state.customer is not None


def go(page):
    st.session_state.page = page
    st.rerun()


def require_sign_in(action="continue"):
    if signed_in():
        return True

    st.warning(
        f"Please sign in or create an account to {action}. "
        "You can still browse designs as a guest."
    )

    if st.button("Sign In / Create Account", key=f"signin_required_{action}"):
        st.session_state.auth_notice = f"Sign in to {action}."
        go("account")

    return False


def get_payment_options():
    options = []

    if setting("cash_payment_enabled", "true").lower() == "true":
        options.append("Cash on Delivery")

    if setting("online_payment_enabled", "false").lower() == "true":
        options.append("Online Payment")

    # Retain manual transfer as a separately configurable option.
    if setting("manual_transfer_enabled", "true").lower() == "true":
        options.append("Manual Online Transfer")

    return options or ["Cash on Delivery"]


def render_image(product):
    image = get_product_image(product)

    if image:
        safe_src = html.escape(image, quote=True)
        st.markdown(
            f'<div class="product-image"><img src="{safe_src}" '
            'alt="Crochet design"></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="product-image" style="font-size:4rem">🧶</div>',
            unsafe_allow_html=True
        )


# ---------------- SESSION STATE ----------------

defaults = {
    "page": "welcome",
    "cart": {},
    "last_order_code": "",
    "last_order_email": "",
    "customer": None,
    "auth_notice": "",
    "guest_mode": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ---------------- HEADER / NAVIGATION ----------------

store_name = setting("store_name", "Croshia Studio")

st.markdown(f"""
<div style="padding-top:12px;padding-bottom:8px">
  <div style="color:#985B75;font-size:1.45rem;font-weight:700">
    🧶 {html.escape(store_name)}
  </div>
  <div style="color:#907D86;font-size:.85rem">
    Handcrafted with love and care
  </div>
</div>
""", unsafe_allow_html=True)

if signed_in():
    st.caption(
        f"Signed in as {st.session_state.customer['name']} · "
        f"{st.session_state.customer['email']}"
    )
else:
    st.caption("Welcome to our handmade collection.")

nav_pages = [
    ("🏠 Shop", "shop"),
    ("🛒 Cart", "cart"),
    ("📦 Track Order", "track"),
    ("👤 Account", "account"),
]

nav_cols = st.columns(len(nav_pages))

for col, (label, page) in zip(nav_cols, nav_pages):
    with col:
        if st.button(label, key=f"nav_{page}", use_container_width=True):
            if page in ("cart", "track"):
                if require_sign_in(
                    "use your cart" if page == "cart" else "track your orders"
                ):
                    go(page)
            else:
                if page == "shop":
                    st.session_state.guest_mode = not signed_in()
                go(page)

st.divider()

# ---------------- ACCOUNT ----------------

if st.session_state.page == "account":
    st.title("Your Croshia Account")

    if signed_in():
        customer = st.session_state.customer

        st.success(f"You're signed in as {customer['name']}.")
        st.write("**Email:**", customer["email"])

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Browse Designs", use_container_width=True):
                go("shop")

        with col2:
            if st.button("Sign Out", use_container_width=True):
                st.session_state.customer = None
                st.session_state.cart = {}
                st.session_state.last_order_code = ""
                st.session_state.last_order_email = ""
                st.session_state.guest_mode = True
                go("shop")

    else:
        if st.session_state.auth_notice:
            st.info(st.session_state.auth_notice)

        tab_signin, tab_signup = st.tabs(
            ["Sign In", "Create Account"]
        )

        with tab_signin:
            with st.form("customer_signin_form"):
                login_email = st.text_input("Email address")
                login_password = st.text_input(
                    "Password", type="password"
                )
                signin = st.form_submit_button(
                    "Sign In", use_container_width=True
                )

            if signin:
                with db() as con:
                    row = con.execute("""
                        SELECT id,name,email,password_hash
                        FROM customers
                        WHERE lower(email)=?
                    """, (login_email.strip().lower(),)).fetchone()

                if row and verify_password(
                    login_password, row["password_hash"]
                ):
                    st.session_state.customer = {
                        "id": row["id"],
                        "name": row["name"],
                        "email": row["email"],
                    }
                    st.session_state.guest_mode = False
                    st.session_state.auth_notice = ""
                    go("shop")
                else:
                    st.error("Email or password is incorrect.")

        with tab_signup:
            with st.form("customer_signup_form"):
                signup_name = st.text_input("Full name")
                signup_email = st.text_input("Email address")
                signup_password = st.text_input(
                    "Create password", type="password"
                )
                signup_confirm = st.text_input(
                    "Confirm password", type="password"
                )
                signup = st.form_submit_button(
                    "Create Account", use_container_width=True
                )

            if signup:
                if not signup_name.strip():
                    st.error("Please enter your name.")
                elif not email_valid(signup_email):
                    st.error("Please enter a valid email address.")
                elif len(signup_password) < 8:
                    st.error("Use a password with at least 8 characters.")
                elif signup_password != signup_confirm:
                    st.error("The passwords do not match.")
                else:
                    try:
                        with db() as con:
                            cur = con.execute("""
                                INSERT INTO customers(name,email,password_hash)
                                VALUES(?,?,?)
                            """, (
                                signup_name.strip(),
                                signup_email.strip().lower(),
                                hash_password(signup_password)
                            ))
                            customer_id = cur.lastrowid

                        st.session_state.customer = {
                            "id": customer_id,
                            "name": signup_name.strip(),
                            "email": signup_email.strip().lower(),
                        }
                        st.session_state.guest_mode = False
                        go("shop")

                    except sqlite3.IntegrityError:
                        st.error(
                            "An account with this email already exists. "
                            "Please sign in."
                        )

        st.caption(
            "Passwords are stored as secure hashes. "
            "Do not reuse passwords from other websites."
        )

    st.stop()

# ---------------- WELCOME ----------------

if st.session_state.page == "welcome":
    st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">Small stitches · Big feelings</div>
      <div class="hero-title">
        Handmade treasures,<br>made to make you smile.
      </div>
      <div class="hero-copy">{html.escape(setting("about"))}</div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader(f"Welcome to {html.escape(store_name)}")
    st.write(
        "Explore handmade crochet designs, find something special, "
        "and place your order with ease."
    )

    left, right = st.columns(2)

    with left:
        if st.button("👤 Sign In / Create Account", use_container_width=True):
            go("account")

    with right:
        if st.button("🧶 View Designs as Guest", use_container_width=True):
            st.session_state.guest_mode = True
            go("shop")

    st.stop()

# ---------------- SHOP ----------------

if st.session_state.page == "shop":
    st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">Small stitches · Big feelings</div>
      <div class="hero-title">
        Handmade treasures,<br>made to make you smile.
      </div>
      <div class="hero-copy">{html.escape(setting("about"))}</div>
    </div>
    """, unsafe_allow_html=True)

    if not signed_in():
        st.info(
            "Guest preview: browse designs and prices. "
            "Sign in to add items to your cart and place an order."
        )

        left, right = st.columns(2)

        with left:
            if st.button("Sign In / Create Account", use_container_width=True):
                go("account")

        with right:
            if st.button("Back to Welcome", use_container_width=True):
                go("welcome")

    products = get_products()
    categories = ["All"] + sorted({
        product["category"] or "Handmade" for product in products
    })

    col1, col2 = st.columns([2, 1])

    with col1:
        chosen_category = st.selectbox("Explore by category", categories)

    with col2:
        search = st.text_input(
            "Search creations",
            placeholder="Flowers, bags, toys..."
        )

    filtered = [
        product for product in products
        if (
            chosen_category == "All"
            or product["category"] == chosen_category
        )
        and search.lower() in (
            product["name"] + " "
            + (product["description"] or "") + " "
            + (product["category"] or "")
        ).lower()
    ]

    st.subheader("Made with care, picked by you")

    if not filtered:
        st.info("No products match your search.")

    cols = st.columns(3)

    for i, product in enumerate(filtered):
        with cols[i % 3]:
            st.markdown('<div class="product-card">', unsafe_allow_html=True)
            render_image(product)

            st.markdown(
                f'<div class="product-name">{html.escape(product["name"])}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="product-description">'
                f'{html.escape(product["description"] or "")}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="product-price">'
                f'{money(product["price"])}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="muted">'
                f'{html.escape(product["category"] or "Handmade")}</div>',
                unsafe_allow_html=True
            )
            st.markdown('</div>', unsafe_allow_html=True)

            if signed_in():
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
                            "qty": 1,
                        }

                    st.toast(f"{product['name']} added to cart.")

            else:
                if st.button(
                    "Sign in to Order",
                    key=f"guest_add_{product['id']}",
                    use_container_width=True
                ):
                    st.session_state.auth_notice = (
                        "Sign in to add designs to your cart."
                    )
                    go("account")

# ---------------- CART / CHECKOUT ----------------

elif st.session_state.page == "cart":
    if not require_sign_in("use your cart"):
        st.stop()

    st.title("Your Shopping Cart")
    cart = st.session_state.cart

    if not cart:
        st.info("Your cart is empty.")

        if st.button("Explore Collection"):
            go("shop")

        st.stop()

    products_by_id = {
        str(product["id"]): product
        for product in get_products(active_only=False)
    }

    subtotal = 0.0

    for pid, item in list(cart.items()):
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

        with col1:
            st.write(f"**{item['name']}**")
            st.caption(f"{money(item['price'])} each")

        with col2:
            st.write(f"Qty: {item['qty']}")

        with col3:
            st.write(money(item["price"] * item["qty"]))

        with col4:
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

    delivery_enabled = setting("delivery_enabled", "true").lower() == "true"
    pickup_enabled = setting("pickup_enabled", "true").lower() == "true"

    fulfillment_options = []

    if delivery_enabled:
        fulfillment_options.append("Delivery")

    if pickup_enabled:
        fulfillment_options.append("Pickup")

    if not fulfillment_options:
        st.error("Ordering is temporarily unavailable. Please contact the store.")
        st.stop()

    payment_options = get_payment_options()

    with st.form("checkout_form"):
        customer = st.session_state.customer

        customer_name = st.text_input(
            "Full name *", value=customer["name"]
        )
        email = st.text_input(
            "Email address *", value=customer["email"]
        )
        phone = st.text_input("Phone number *", placeholder="03001234567")

        fulfillment = st.radio(
            "How would you like to receive your order?",
            fulfillment_options,
            horizontal=True
        )

        address = (
            st.text_area("Complete delivery address *")
            if fulfillment == "Delivery" else ""
        )

        if fulfillment == "Pickup":
            st.info(setting("pickup_note"))
            pickup_note = st.text_input(
                "Pickup name or preferred contact (optional)"
            )
        else:
            pickup_note = ""

        payment_method = st.radio(
            "Payment method",
            payment_options,
            horizontal=False
        )

        if payment_method == "Manual Online Transfer":
            st.markdown(f"#### {setting('payment_title', 'Payment Instructions')}")
            st.write("**Account name:**", setting("payment_name"))
            st.write("**Provider:**", setting("payment_method"))
            st.code(setting("payment_details"))
            st.info(setting("payment_instructions"))
            st.caption(
                "This is a manual transfer. Payment must be confirmed by "
                "the store before the order is marked paid."
            )

        elif payment_method == "Online Payment":
            checkout_url = setting("gateway_checkout_url", "")

            st.info(
                "Online payment has been selected. Continue only through "
                "the store's configured secure payment provider."
            )

            if checkout_url:
                st.markdown(
                    f"[Open secure payment provider]({checkout_url})"
                )
            else:
                st.warning(
                    "The store has not configured a payment-provider checkout "
                    "URL yet. Do not enter card details on this website."
                )

        place_order = st.form_submit_button(
            "Place Order", use_container_width=True
        )

        if place_order:
            if not customer_name.strip():
                st.error("Please enter your full name.")

            elif not email_valid(email):
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

            elif (
                payment_method == "Online Payment"
                and not setting("gateway_checkout_url", "").strip()
            ):
                st.error(
                    "Secure checkout is not configured yet. "
                    "Please choose another available payment method."
                )

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
                        if fulfillment == "Delivery" else 0.0
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
                            "qty": int(item["qty"]),
                        }
                        for item in st.session_state.cart.values()
                    ]

                    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                    expected_date = (
                        date.today() + timedelta(days=7)
                    ).isoformat()

                    try:
                        with db() as con:
                            con.execute("""
                                INSERT INTO orders(
                                    order_code,customer_name,email,phone,
                                    fulfillment,address,pickup_note,
                                    payment_method,payment_status,items_json,
                                    subtotal,delivery_fee,total_amount,status,
                                    admin_message,expected_date,created_at
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
                                created_at,
                            ))

                            for item in items:
                                row = con.execute(
                                    "SELECT stock FROM products WHERE id=?",
                                    (item["product_id"],)
                                ).fetchone()

                                if row and int(row["stock"]) > 0:
                                    con.execute("""
                                        UPDATE products
                                        SET stock=MAX(0,stock-?)
                                        WHERE id=?
                                    """, (
                                        item["qty"], item["product_id"]
                                    ))

                        st.session_state.cart = {}
                        st.session_state.last_order_code = order_code
                        st.session_state.last_order_email = email.strip().lower()
                        st.session_state.page = "track"
                        st.rerun()

                    except sqlite3.Error:
                        st.error(
                            "We could not save your order. Your cart "
                            "has not been cleared. Please try again."
                        )

# ---------------- ORDER TRACKING ----------------

elif st.session_state.page == "track":
    if not require_sign_in("track your orders"):
        st.stop()

    st.title("Track Your Order")
    st.write(
        "Enter your order ID and checkout email to see the latest status."
    )

    customer_email = st.session_state.customer["email"].lower()

    if (
        st.session_state.last_order_code
        and st.session_state.last_order_email == customer_email
    ):
        st.success(
            f"Order placed successfully! Your ID is "
            f"**{st.session_state.last_order_code}**"
        )

    with st.form("track_order_form"):
        order_code = st.text_input(
            "Order ID",
            value=st.session_state.last_order_code
        )
        email = st.text_input(
            "Checkout email", value=customer_email
        )
        track = st.form_submit_button("View Order")

    if track or (
        st.session_state.last_order_code
        and st.session_state.last_order_email == customer_email
    ):
        code_to_find = (
            order_code if track else st.session_state.last_order_code
        ).strip().upper()

        email_to_find = (
            email if track else customer_email
        ).strip().lower()

        if email_to_find != customer_email:
            st.warning(
                "You can only view orders linked to the email "
                "address on your signed-in account."
            )

        else:
            with db() as con:
                row = con.execute("""
                    SELECT * FROM orders
                    WHERE upper(order_code)=? AND lower(email)=?
                """, (
                    code_to_find, customer_email
                )).fetchone()

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
                    for item in json.loads(order["items_json"] or "[]"):
                        st.write(
                            f"• {item['name']} × {item['qty']} — "
                            f"{money(item['price'] * item['qty'])}"
                        )
                except (ValueError, TypeError, KeyError):
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

                st.caption("Keep your order ID and account email private.")

            elif track:
                st.warning(
                    "No matching order found. Check your order ID "
                    "and signed-in email."
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
