# 🧶 Croshia Studio

Croshia Studio is a handmade crochet shopping and order management application built with Python and Streamlit.

## Features

- 🛍️ Browse handmade designs
- 🛒 Shopping cart and checkout
- 📦 Customer order tracking
- 🧾 Admin order management
- 🎨 Add and edit products
- 📊 Revenue and inventory dashboard
- 💳 Payment settings
- ⚙️ Store configuration

## Tech Stack

- Python
- Streamlit
- SQLite (local development)
- Supabase / PostgreSQL (planned for online shared storage)

## Project Structure

```text
Croshia-Studio/
├── app.py
├── admin_app.py
├── requirements.txt
└── README.md
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the customer store:

```bash
python -m streamlit run app.py
```

Start the admin dashboard in a second terminal:

```bash
python -m streamlit run admin_app.py --server.port 8502
```

Customer store: http://localhost:8501

Admin dashboard: http://localhost:8502

## Database

The local development version uses `croshia.db`. Both apps must use the same database file to share orders.

For separate online deployments, configure a shared Supabase database and connect both apps to it.

## Security

- Keep database credentials and API keys private.
- Change the default admin password before deployment.
- Never store customers' full card numbers, CVVs, or card PINs.
- Use a secure payment provider for real online payments.

## Developer

Ahmed Faisal

Built with Python and Streamlit.
