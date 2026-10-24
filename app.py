import base64
import hashlib
import hmac
import html
import json
import os
import secrets
from datetime import date, datetime, timedelta, timezone

import extra_streamlit_components as stx
import streamlit as st
from supabase import create_client, Client


# ============================================================
# CROSHIA STUDIO CUSTOMER STORE — SUPABASE VERSION
# Requires Supabase tables created using the SQL provided earlier.
# Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.
# Never commit secrets to GitHub.
# ============================================================

st.set_page_config(
    page_title="Croshia Studio | Handmade with Love",
    page_icon="🧶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Supabase is not configured. In Streamlit Cloud, open "
        "App settings → Secrets and add SUPABASE_URL and "
        "SUPABASE_SERVICE_ROLE_KEY."
    )
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as exc:
    st.error(f"Could not connect to Supabase: {exc}")
    st.stop()


# ---------------- STYLE ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');
:root { --rose:#BD7895; --rose-dark:#985B75; --cream:#FFFAF6; --ink:#332A31; }
.stApp { background:var(--cream); color:var(--ink); font-family:'DM Sans',sans-serif; }
h1,h2,h3 { font-family:'Playfair Display',serif !important; }
h1 { color:var(--rose-dark) !important; }
.block-container { max-width:1250px; padding-top:1.5rem; padding-bottom:3rem; }
.stButton>button,.stFormSubmitButton>button { background:var(--rose)!important; color:white!important; border:none!important; border-radius:10px!important; font-weight:700!important; min-height:2.6rem; }
.stButton>button:hover,.stFormSubmitButton>button:hover { background:var(--rose-dark)!important; }
[data-testid="stMetric"] { background:white; border:1px solid #EFDEE5; padding:14px; border-radius:14px; }
.hero { background:linear-gradient(115deg,#F3DFE7,#FFF5ED); padding:30px; border-radius:20px; margin:10px 0 22px; }
.hero-kicker { color:#8C586F; text-transform:uppercase; letter-spacing:2px; font-size:.75rem; font-weight:700; }
.hero-title { font-family:'Playfair Display',serif; font-size:2.35rem; line-height:1.15; color:#493540; margin:8px 0; }
.hero-copy { color:#725F68; }
.product-card { background:white; border:1px solid #EFE2E6; border-radius:16px; padding:13px; margin-bottom:8px; box-shadow:0 5px 18px #6F46500B; }
.product-image { height:230px; border-radius:11px; background:#F7EEF0; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.product-image img { width:100%; height:100%; object-fit:cover; }
.product-name { font-weight:700; font-size:1.04rem; margin-top:10px; }
.product-description { color:#786E74; font-size:.88rem; min-height:38px; }
.product-price { color:var(--rose-dark); font-weight:700; font-size:1.05rem; margin:8px 0; }
.muted { color:#786E74; font-size:.88rem; }
@media(max-width:650px) { .hero { padding:20px; } .hero-title { font-size:1.8rem; } .product-image { height:175px; } }
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE HELPERS ----------------

def db_select(table, columns="*", **filters):
    query = supabase.table(table).select(columns)
    for key, value in filters.items():
        query = query.eq(key, value)
    return query.execute().data or []


def setting(key, default=""):
    aliases = {
        "delivery_fee": ("delivery_fee", "delivery_charge"),
        "payment_name": ("payment_name", "payment_account_name"),
        "payment_method": ("payment_method", "payment_provider"),
        "payment_details": ("payment_details", "payment_account_details"),
        "payment_instructions": ("payment_instructions",),
        "pickup_note": ("pickup_note",),
    }
    for candidate in aliases.get(key, (key,)):
        try:
            rows = db_select("settings", "value", key=candidate)
            if rows and rows[0].get("value") not in (None, ""):
                return str(rows[0]["value"])
        except Exception:
            continue
    return default


def get_products(active_only=True):
    query = supabase.table("products").select("*").order("id", desc=True)
    if active_only:
        query = query.eq("active", True)
    return query.execute().data or []


def get_product_image(product):
    if product.get("image_data"):
        return "data:image/jpeg;base64," + product["image_data"]
    return product.get("image_url") or ""


def money(amount):
    try:
        return f"PKR {float(amount or 0):,.0f}"
    except (ValueError, TypeError):
        return "PKR 0"


def email_valid(email):
    email = email.strip()
    return "@" in email and "." in email.split("@")[-1] and " " not in email


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
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
    except (ValueError, TypeError, AttributeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    if setting("manual_transfer_enabled", "true").lower() == "true":
        options.append("Manual Online Transfer")
    return options or ["Cash on Delivery"]


def render_image(product):
    image = get_product_image(product)
    if image:
        safe_src = html.escape(image, quote=True)
        st.markdown(
            f'<div class="product-image"><img src="{safe_src}" alt="Crochet design"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="product-image" style="font-size:4rem">🧶</div>',
            unsafe_allow_html=True,
        )


# ---------------- SESSION / COOKIE LOGIN ----------------

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

cookie_manager = stx.CookieManager(key="croshia_persistent_login_cookie_manager")
try:
    browser_cookies = cookie_manager.get_all()
except Exception:
    browser_cookies = None

if browser_cookies is None:
    st.info("Loading your saved session…")
    st.stop()


def create_persistent_session(customer_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        # Revoke previous sessions for this customer so the newest login is active.
        supabase.table("customer_sessions").delete().eq("customer_id", int(customer_id)).execute()
        supabase.table("customer_sessions").insert({
            "token_hash": token_hash(token),
            "customer_id": int(customer_id),
            "expires_at": expires_at.isoformat(),
        }).execute()
        cookie_manager.set(
            "croshia_customer_session",
            token,
            expires_at=datetime.now() + timedelta(days=30),
            key="croshia_save_customer_session",
        )
    except Exception:
        st.warning("Login worked, but the remember-me session could not be saved.")


def restore_persistent_session(cookies):
    token = (cookies or {}).get("croshia_customer_session")
    if not isinstance(token, str) or not token:
        return False
    try:
        sessions = db_select("customer_sessions", "*", token_hash=token_hash(token))
        if not sessions:
            return False
        session = sessions[0]
        expires = datetime.fromisoformat(str(session["expires_at"]).replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            supabase.table("customer_sessions").delete().eq("token_hash", token_hash(token)).execute()
            return False
        customers = db_select("customers", "id,name,email", id=session["customer_id"])
        if not customers:
            return False
        customer = customers[0]
        st.session_state.customer = {
            "id": customer["id"],
            "name": customer["name"],
            "email": customer["email"],
        }
        st.session_state.guest_mode = False
        if st.session_state.page == "welcome":
            st.session_state.page = "shop"
        return True
    except Exception:
        return False


def end_persistent_session():
    try:
        token = cookie_manager.get("croshia_customer_session")
        if isinstance(token, str) and token:
            supabase.table("customer_sessions").delete().eq(
                "token_hash", token_hash(token)
            ).execute()
    except Exception:
        pass
    try:
        cookie_manager.delete(
            "croshia_customer_session", key="croshia_delete_customer_session"
        )
    except Exception:
        pass


if st.session_state.customer is None:
    restore_persistent_session(browser_cookies)


# ---------------- HEADER / NAVIGATION ----------------

store_name = setting("store_name", "Croshia Studio")
st.markdown(f"""
<div style="padding-top:12px;padding-bottom:8px">
  <div style="color:#985B75;font-size:1.45rem;font-weight:700">🧶 {html.escape(store_name)}</div>
  <div style="color:#907D86;font-size:.85rem">Handcrafted with love and care</div>
</div>
""", unsafe_allow_html=True)

if signed_in():
    st.caption(
        f"Signed in as {st.session_state.customer['name']} · "
        f"{st.session_state.customer['email']}"
    )
else:
    st.caption("Welcome to our handmade collection.")

nav_pages = [("🏠 Shop", "shop"), ("🛒 Cart", "cart"), ("📦 Track Order", "track"), ("👤 Account", "account")]
nav_cols = st.columns(len(nav_pages))
for col, (label, page) in zip(nav_cols, nav_pages):
    with col:
        if st.button(label, key=f"nav_{page}", use_container_width=True):
            if page in ("cart", "track"):
                if require_sign_in("use your cart" if page == "cart" else "track your orders"):
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
                end_persistent_session()
                st.session_state.customer = None
                st.session_state.cart = {}
                st.session_state.last_order_code = ""
                st.session_state.last_order_email = ""
                st.session_state.guest_mode = True
                go("shop")
    else:
        if st.session_state.auth_notice:
            st.info(st.session_state.auth_notice)
        tab_signin, tab_signup = st.tabs(["Sign In", "Create Account"])
        with tab_signin:
            with st.form("customer_signin_form"):
                login_email = st.text_input("Email address")
                login_password = st.text_input("Password", type="password")
                signin = st.form_submit_button("Sign In", use_container_width=True)
            if signin:
                try:
                    rows = supabase.table("customers").select(
                        "id,name,email,password_hash"
                    ).ilike("email", login_email.strip()).limit(1).execute().data or []
                    row = rows[0] if rows else None
                    if row and verify_password(login_password, row.get("password_hash", "")):
                        st.session_state.customer = {
                            "id": row["id"], "name": row["name"], "email": row["email"]
                        }
                        st.session_state.guest_mode = False
                        st.session_state.auth_notice = ""
                        create_persistent_session(row["id"])
                        go("shop")
                    else:
                        st.error("Email or password is incorrect.")
                except Exception:
                    st.error("Could not sign in right now. Please try again.")
        with tab_signup:
            with st.form("customer_signup_form"):
                signup_name = st.text_input("Full name")
                signup_email = st.text_input("Email address")
                signup_password = st.text_input("Create password", type="password")
                signup_confirm = st.text_input("Confirm password", type="password")
                signup = st.form_submit_button("Create Account", use_container_width=True)
            if signup:
                clean_email = signup_email.strip().lower()
                if not signup_name.strip():
                    st.error("Please enter your name.")
                elif not email_valid(clean_email):
                    st.error("Please enter a valid email address.")
                elif len(signup_password) < 8:
                    st.error("Use a password with at least 8 characters.")
                elif signup_password != signup_confirm:
                    st.error("The passwords do not match.")
                else:
                    try:
                        rows = supabase.table("customers").insert({
                            "name": signup_name.strip(),
                            "email": clean_email,
                            "password_hash": hash_password(signup_password),
                        }).execute().data or []
                        if not rows:
                            raise RuntimeError("Account could not be created.")
                        customer_id = rows[0]["id"]
                        st.session_state.customer = {
                            "id": customer_id,
                            "name": signup_name.strip(),
                            "email": clean_email,
                        }
                        st.session_state.guest_mode = False
                        create_persistent_session(customer_id)
                        go("shop")
                    except Exception:
                        st.error("Could not create this account. The email may already be registered.")
        st.caption("Passwords are stored as secure hashes. Do not reuse passwords from other websites.")
    st.stop()


# ---------------- WELCOME ----------------

if st.session_state.page == "welcome":
    st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">Small stitches · Big feelings</div>
      <div class="hero-title">Handmade treasures,<br>made to make you smile.</div>
      <div class="hero-copy">{html.escape(setting("about", "Beautiful crochet creations, handmade with love."))}</div>
    </div>
    """, unsafe_allow_html=True)
    st.subheader(f"Welcome to {html.escape(store_name)}")
    st.write("Explore handmade crochet designs, find something special, and place your order with ease.")
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
      <div class="hero-title">Handmade treasures,<br>made to make you smile.</div>
      <div class="hero-copy">{html.escape(setting("about", "Beautiful crochet creations, handmade with love."))}</div>
    </div>
    """, unsafe_allow_html=True)
    if not signed_in():
        st.info("Guest preview: browse designs and prices. Sign in to add items to your cart and place an order.")
        left, right = st.columns(2)
        with left:
            if st.button("Sign In / Create Account", use_container_width=True):
                go("account")
        with right:
            if st.button("Back to Welcome", use_container_width=True):
                go("welcome")

    try:
        products = get_products()
    except Exception as exc:
        st.error("Could not load products from Supabase. Check that the SQL tables exist.")
        st.caption(str(exc))
        st.stop()

    categories = ["All"] + sorted({str(p.get("category") or "Handmade") for p in products})
    col1, col2 = st.columns([2, 1])
    with col1:
        chosen_category = st.selectbox("Explore by category", categories)
    with col2:
        search = st.text_input("Search creations", placeholder="Flowers, bags, toys...")

    filtered = [
        p for p in products
        if (chosen_category == "All" or (p.get("category") or "Handmade") == chosen_category)
        and search.lower() in (
            str(p.get("name") or "") + " " + str(p.get("description") or "") + " " + str(p.get("category") or "")
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
            st.markdown(f'<div class="product-name">{html.escape(str(product.get("name") or ""))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-description">{html.escape(str(product.get("description") or ""))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-price">{money(product.get("price"))}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="muted">{html.escape(str(product.get("category") or "Handmade"))}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if signed_in():
                if st.button("Add to Cart ＋", key=f"add_{product['id']}", use_container_width=True):
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
                if st.button("Sign in to Order", key=f"guest_add_{product['id']}", use_container_width=True):
                    st.session_state.auth_notice = "Sign in to add designs to your cart."
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

    try:
        products_by_id = {str(p["id"]): p for p in get_products(active_only=False)}
    except Exception:
        st.error("Could not check product availability. Please try again.")
        st.stop()

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
        customer_name = st.text_input("Full name *", value=customer["name"])
        email = st.text_input("Email address *", value=customer["email"])
        phone = st.text_input("Phone number *", placeholder="03001234567")
        fulfillment = st.radio("How would you like to receive your order?", fulfillment_options, horizontal=True)
        address = st.text_area("Complete delivery address *") if fulfillment == "Delivery" else ""
        if fulfillment == "Pickup":
            st.info(setting("pickup_note", "Pickup instructions will be shared after confirmation."))
            pickup_note = st.text_input("Pickup name or preferred contact (optional)")
        else:
            pickup_note = ""
        payment_method = st.radio("Payment method", payment_options, horizontal=False)
        if payment_method == "Manual Online Transfer":
            st.markdown(f"#### {setting('payment_title', 'Payment Instructions')}")
            st.write("**Account name:**", setting("payment_name", "Croshia Studio"))
            st.write("**Provider:**", setting("payment_method", "Bank Transfer"))
            st.code(setting("payment_details", "Contact the store for payment details."))
            st.info(setting("payment_instructions", "Contact the store after making your transfer."))
            st.caption("This is a manual transfer. The store must confirm payment before marking it paid.")
        elif payment_method == "Online Payment":
            checkout_url = setting("gateway_checkout_url", "").strip()
            st.info("Continue only through the store's configured secure payment provider.")
            if checkout_url:
                st.markdown(f"[Open secure payment provider]({checkout_url})")
            else:
                st.warning("The store has not configured a payment-provider checkout URL yet. Do not enter card details on this website.")
        place_order = st.form_submit_button("Place Order", use_container_width=True)

        if place_order:
            clean_email = email.strip().lower()
            clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
            if not customer_name.strip():
                st.error("Please enter your full name.")
            elif not email_valid(clean_email):
                st.error("Please enter a valid email address.")
            elif not clean_phone.isdigit() or len(clean_phone) < 7:
                st.error("Please enter a valid phone number.")
            elif fulfillment == "Delivery" and not address.strip():
                st.error("Please enter your delivery address.")
            elif not st.session_state.cart:
                st.error("Your cart is empty.")
            elif payment_method == "Online Payment" and not setting("gateway_checkout_url", "").strip():
                st.error("Secure checkout is not configured yet. Please choose another available payment method.")
            else:
                unavailable = []
                latest_subtotal = 0.0
                order_items = []
                for pid, item in st.session_state.cart.items():
                    product = products_by_id.get(pid)
                    if not product or not product.get("active", True):
                        unavailable.append(item["name"])
                        continue
                    stock = int(product.get("stock") or 0)
                    qty = int(item["qty"])
                    if stock > 0 and stock < qty:
                        unavailable.append(item["name"])
                    latest_price = float(product.get("price") or 0)
                    latest_subtotal += latest_price * qty
                    order_items.append({
                        "product_id": int(product["id"]),
                        "name": product["name"],
                        "price": latest_price,
                        "qty": qty,
                    })

                if unavailable:
                    st.error("Please check availability for: " + ", ".join(unavailable))
                elif not order_items:
                    st.error("Your cart has no available items.")
                else:
                    delivery_fee = float(setting("delivery_fee", "200") or 0) if fulfillment == "Delivery" else 0.0
                    total = latest_subtotal + delivery_fee
                    order_code = "CRS-" + datetime.now().strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()
                    expected_date = (date.today() + timedelta(days=7)).isoformat()
                    new_order = {
                        "order_code": order_code,
                        "customer_name": customer_name.strip(),
                        "email": clean_email,
                        "phone": phone.strip(),
                        "fulfillment": fulfillment,
                        "address": address.strip(),
                        "pickup_note": pickup_note.strip(),
                        "payment_method": payment_method,
                        "payment_status": "Unpaid",
                        "items_json": order_items,
                        "subtotal": latest_subtotal,
                        "delivery_fee": delivery_fee,
                        "total_amount": total,
                        "status": "New",
                        "admin_message": "Thank you! Your order has been received. We will confirm your order shortly.",
                        "expected_date": expected_date,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        # Save the order first. For a small store this is convenient;
                        # for high traffic, move order+stock changes into a SQL function transaction.
                        supabase.table("orders").insert(new_order).execute()
                        for item in order_items:
                            product = products_by_id.get(str(item["product_id"]), {})
                            stock = int(product.get("stock") or 0)
                            if stock > 0:
                                supabase.table("products").update({
                                    "stock": max(0, stock - int(item["qty"]))
                                }).eq("id", item["product_id"]).execute()
                        st.session_state.cart = {}
                        st.session_state.last_order_code = order_code
                        st.session_state.last_order_email = clean_email
                        st.session_state.page = "track"
                        st.rerun()
                    except Exception:
                        st.error("We could not save your order. Your cart has not been cleared. Please try again.")


# ---------------- ORDER TRACKING ----------------

elif st.session_state.page == "track":
    if not require_sign_in("track your orders"):
        st.stop()
    st.title("Track Your Order")
    st.write("Enter your order ID and checkout email to see the latest status.")
    customer_email = st.session_state.customer["email"].lower()

    if st.session_state.last_order_code and st.session_state.last_order_email == customer_email:
        st.success(f"Order placed successfully! Your ID is **{st.session_state.last_order_code}**")

    with st.form("track_order_form"):
        order_code = st.text_input("Order ID", value=st.session_state.last_order_code)
        email = st.text_input("Checkout email", value=customer_email)
        track = st.form_submit_button("View Order")

    if track or (st.session_state.last_order_code and st.session_state.last_order_email == customer_email):
        code_to_find = (order_code if track else st.session_state.last_order_code).strip().upper()
        email_to_find = (email if track else customer_email).strip().lower()
        if email_to_find != customer_email:
            st.warning("You can only view orders linked to the email address on your signed-in account.")
        else:
            try:
                rows = supabase.table("orders").select("*").eq(
                    "order_code", code_to_find
                ).ilike("email", customer_email).limit(1).execute().data or []
                order = rows[0] if rows else None
            except Exception:
                order = None
                st.error("Could not load this order right now. Please try again.")
            if order:
                a, b, c = st.columns(3)
                a.metric("Order Total", money(order.get("total_amount")))
                b.metric("Order Status", order.get("status", "New"))
                c.metric("Payment Status", order.get("payment_status", "Unpaid"))
                st.write("**Order ID:**", order.get("order_code", ""))
                st.write("**Order date:**", order.get("created_at", ""))
                st.write("**Fulfillment:**", order.get("fulfillment", ""))
                if order.get("address"):
                    st.write("**Delivery address:**", order["address"])
                if order.get("expected_date"):
                    st.write("**Expected completion / delivery:**", order["expected_date"])
                st.subheader("Your Items")
                items = order.get("items_json") or []
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except json.JSONDecodeError:
                        items = []
                for item in items:
                    qty = int(item.get("qty", item.get("quantity", 1)) or 1)
                    st.write(f"• {item.get('name', item.get('title', 'Item'))} × {qty} — {money(float(item.get('price', 0)) * qty)}")
                if order.get("status") in ("Delivered", "Completed"):
                    st.success("Your order has been completed.")
                elif order.get("status") == "Cancelled":
                    st.warning("This order has been cancelled.")
                else:
                    st.info("Your order is being processed.")
                st.subheader("Message from Croshia Studio")
                st.write(order.get("admin_message") or "There are no additional updates yet.")
                st.caption("Keep your order ID and account email private.")
            elif track:
                st.warning("No matching order found. Check your order ID and signed-in email.")

    if st.button("Continue Shopping"):
        go("shop")


# ---------------- FOOTER ----------------

st.divider()
st.markdown("""
<div style="text-align:center;color:#907D86;font-size:.85rem">
  🧶 Croshia Studio · Handmade with love · Pakistan
</div>
""", unsafe_allow_html=True)
