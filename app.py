from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)
from functools import wraps
from datetime import datetime
from urllib.parse import quote
from werkzeug.utils import secure_filename

import sqlite3
import os
import uuid


# ============================================================
# RUTHELYN COLLECTIONS - FLASK ECOMMERCE APPLICATION
# ============================================================

app = Flask(__name__)

# ------------------------------------------------------------
# SECRET KEY
# ------------------------------------------------------------
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "ruthelyn-development-secret-key-change-in-render"
)

# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "ruthelyn.db")

# ------------------------------------------------------------
# UPLOADS
# ------------------------------------------------------------
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------------------------------------------------
# STORE INFORMATION
# ------------------------------------------------------------
BUSINESS_NAME = "RUTHELYN COLLECTIONS"

WHATSAPP_NUMBER = os.environ.get(
    "WHATSAPP_NUMBER",
    "2348125506022"
)

PHONE_NUMBER = os.environ.get(
    "PHONE_NUMBER",
    "08125506022"
    "08153984064"
)

# ------------------------------------------------------------
# ALLOWED IMAGE TYPES
# ------------------------------------------------------------
ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def db():
    """
    Open SQLite database connection.
    """
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """
    Create database tables if they do not exist.
    """

    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            old_price REAL,
            description TEXT,
            image TEXT,
            featured INTEGER DEFAULT 0,
            sizes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            size TEXT,
            quantity INTEGER DEFAULT 1,
            payment_method TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

    connection.commit()
    connection.close()


# Initialize database when Flask/Gunicorn imports the app.
init_db()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed(filename):
    """
    Check whether an uploaded file has an allowed extension.
    """

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


def default_sizes(category):
    """
    Automatically provide sizes according to product category.
    """

    category_lower = category.lower()

    if category_lower == "luxury wears":
        return "8,10,12,14"

    if category_lower == "shoes":
        return "38,39,40,41,42,43,44,45,46"

    if category_lower == "bags":
        return "One Size"

    if (
        category_lower == "jewellery & accessories"
        or category_lower == "jewellry & accessories"
    ):
        return "One Size"

    return "One Size"


def normalize_category(category):
    """
    Keep the website category spelling consistent.
    """

    if not category:
        return category

    category = category.strip()

    mapping = {
        "Jewellry & Accessories": "Jewellery & Accessories",
        "Jewellery & Accessories": "Jewellery & Accessories",
        "Luxury Wear": "Luxury Wears",
        "Luxury Wears": "Luxury Wears",
        "Shoes": "Shoes",
        "Bags": "Bags"
    }

    return mapping.get(category, category)


def whatsapp_url(message):
    """
    Create WhatsApp URL.
    """

    return (
        f"https://wa.me/{WHATSAPP_NUMBER}"
        f"?text={quote(message)}"
    )


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def admin_required(view_function):

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))

        return view_function(*args, **kwargs)

    return wrapped_view


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    connection = db()

    # --------------------------------------------------------
    # Featured products
    # --------------------------------------------------------
    products = connection.execute("""
        SELECT *
        FROM products
        ORDER BY featured DESC, created_at DESC, id DESC
        LIMIT 8
    """).fetchall()

    # --------------------------------------------------------
    # Latest product with image for each homepage category
    # --------------------------------------------------------

    category_names = [
        "Luxury Wears",
        "Shoes",
        "Bags",
        "Jewellery & Accessories"
    ]

    category_products = {}

    for category in category_names:

        product = connection.execute("""
            SELECT *
            FROM products
            WHERE category = ?
            AND image IS NOT NULL
            AND image != ''
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """, (category,)).fetchone()

        category_products[category] = product

    connection.close()

    return render_template(
        "index.html",
        products=products,
        category_products=category_products
    )


# ============================================================
# SHOP
# ============================================================

@app.route("/shop")
def shop():

    search = request.args.get("q", "").strip()

    category = request.args.get("category", "").strip()

    category = normalize_category(category)

    connection = db()

    if search and category:

        products = connection.execute("""
            SELECT *
            FROM products
            WHERE
                (
                    name LIKE ?
                    OR description LIKE ?
                )
                AND category = ?
            ORDER BY created_at DESC, id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            category
        )).fetchall()

    elif search:

        products = connection.execute("""
            SELECT *
            FROM products
            WHERE
                name LIKE ?
                OR description LIKE ?
            ORDER BY created_at DESC, id DESC
        """, (
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    elif category:

        products = connection.execute("""
            SELECT *
            FROM products
            WHERE category = ?
            ORDER BY created_at DESC, id DESC
        """, (category,)).fetchall()

    else:

        products = connection.execute("""
            SELECT *
            FROM products
            ORDER BY created_at DESC, id DESC
        """).fetchall()

    connection.close()

    categories = [
        "Luxury Wears",
        "Shoes",
        "Bags",
        "Jewellery & Accessories"
    ]

    return render_template(
        "shop.html",
        products=products,
        categories=categories,
        selected_category=category,
        search=search
    )


# ============================================================
# PRODUCT DETAILS
# ============================================================

@app.route("/product/<int:product_id>")
def product(product_id):

    connection = db()

    item = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    connection.close()

    if item is None:
        flash("Product not found.")
        return redirect(url_for("shop"))

    return render_template(
        "product.html",
        product=item
    )


# ============================================================
# CHECKOUT
# ============================================================

@app.route("/checkout/<int:product_id>", methods=["GET", "POST"])
def checkout(product_id):

    connection = db()

    item = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    connection.close()

    if item is None:
        flash("Product not found.")
        return redirect(url_for("shop"))

    sizes = []

    if item["sizes"]:

        sizes = [
            size.strip()
            for size in item["sizes"].split(",")
            if size.strip()
        ]

    if request.method == "POST":

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        size = request.form.get(
            "size",
            ""
        ).strip()

        quantity_text = request.form.get(
            "quantity",
            "1"
        ).strip()

        payment_method = request.form.get(
            "payment_method",
            "Pay on WhatsApp"
        ).strip()

        try:
            quantity = int(quantity_text)

            if quantity < 1:
                quantity = 1

        except ValueError:
            quantity = 1

        if not customer_name:
            flash("Please enter your name.")
            return redirect(
                url_for(
                    "checkout",
                    product_id=product_id
                )
            )

        if not phone:
            flash("Please enter your phone number.")
            return redirect(
                url_for(
                    "checkout",
                    product_id=product_id
                )
            )

        if not address:
            flash("Please enter your delivery address.")
            return redirect(
                url_for(
                    "checkout",
                    product_id=product_id
                )
            )

        # ----------------------------------------------------
        # Save order
        # ----------------------------------------------------

        connection = db()

        cursor = connection.execute("""
            INSERT INTO orders (
                product_id,
                customer_name,
                phone,
                address,
                size,
                quantity,
                payment_method,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            customer_name,
            phone,
            address,
            size,
            quantity,
            payment_method,
            "Pending"
        ))

        order_id = cursor.lastrowid

        connection.commit()
        connection.close()

        # ----------------------------------------------------
        # WhatsApp checkout
        # ----------------------------------------------------

        if payment_method.lower() in {
            "pay on whatsapp",
            "whatsapp",
            "pay via whatsapp"
        }:

            message = (
                f"Hello {BUSINESS_NAME},\n\n"
                f"I would like to place an order.\n\n"
                f"Order ID: #{order_id}\n"
                f"Product: {item['name']}\n"
                f"Category: {item['category']}\n"
                f"Price: ₦{float(item['price']):,.2f}\n"
                f"Size: {size or 'Not specified'}\n"
                f"Quantity: {quantity}\n\n"
                f"Customer Name: {customer_name}\n"
                f"Phone: {phone}\n"
                f"Delivery Address: {address}\n"
            )

            return redirect(
                whatsapp_url(message)
            )

        return render_template(
            "payment.html",
            product=item,
            order_id=order_id,
            customer_name=customer_name,
            quantity=quantity,
            size=size
        )

    return render_template(
        "checkout.html",
        product=item,
        sizes=sizes
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        admin_username = os.environ.get(
            "ADMIN_USERNAME"
        )

        admin_password = os.environ.get(
            "ADMIN_PASSWORD"
        )

        # ----------------------------------------------------
        # Environment variables are required in production.
        # ----------------------------------------------------

        if (
            admin_username
            and admin_password
            and username == admin_username
            and password == admin_password
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin")
            )

        flash(
            "Invalid username or password."
        )

    return render_template(
        "admin_login.html"
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# ADMIN DASHBOARD / PRODUCT UPLOAD
# ============================================================

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():

    if request.method == "POST":

        # ----------------------------------------------------
        # Product information
        # ----------------------------------------------------

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        category = normalize_category(category)

        price_text = request.form.get(
            "price",
            "0"
        ).strip()

        old_price_text = request.form.get(
            "old_price",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        sizes = request.form.get(
            "sizes",
            ""
        ).strip()

        featured = 1 if request.form.get(
            "featured"
        ) else 0

        # ----------------------------------------------------
        # Validate product name
        # ----------------------------------------------------

        if not name:

            flash("Please enter a product name.")

            return redirect(
                url_for("admin")
            )

        # ----------------------------------------------------
        # Validate category
        # ----------------------------------------------------

        if not category:

            flash("Please select a product category.")

            return redirect(
                url_for("admin")
            )

        # ----------------------------------------------------
        # Validate price
        # ----------------------------------------------------

        try:

            price = float(price_text)

            if price < 0:
                raise ValueError

        except ValueError:

            flash("Please enter a valid product price.")

            return redirect(
                url_for("admin")
            )

        # ----------------------------------------------------
        # Old price
        # ----------------------------------------------------

        old_price = None

        if old_price_text:

            try:

                old_price = float(
                    old_price_text
                )

                if old_price < 0:
                    old_price = None

            except ValueError:

                old_price = None

        # ----------------------------------------------------
        # Automatic sizes
        # ----------------------------------------------------

        if not sizes:

            sizes = default_sizes(
                category
            )

        # ----------------------------------------------------
        # IMAGE UPLOAD
        # ----------------------------------------------------

        image = request.files.get(
            "image"
        )

        filename = None

        if image and image.filename:

            if not allowed(
                image.filename
            ):

                flash(
                    "Invalid image format. "
                    "Please upload PNG, JPG, JPEG or WEBP."
                )

                return redirect(
                    url_for("admin")
                )

            original_filename = secure_filename(
                image.filename
            )

            if not original_filename:

                flash(
                    "Invalid image file."
                )

                return redirect(
                    url_for("admin")
                )

            if "." not in original_filename:

                flash(
                    "Invalid image file."
                )

                return redirect(
                    url_for("admin")
                )

            extension = (
                original_filename
                .rsplit(".", 1)[1]
                .lower()
            )

            filename = (
                f"{uuid.uuid4().hex}."
                f"{extension}"
            )

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            try:

                image.save(
                    image_path
                )

            except Exception:

                flash(
                    "There was a problem uploading the image."
                )

                return redirect(
                    url_for("admin")
                )

        # ----------------------------------------------------
        # SAVE PRODUCT
        # ----------------------------------------------------

        connection = db()

        connection.execute("""
            INSERT INTO products (
                name,
                category,
                price,
                old_price,
                description,
                image,
                featured,
                sizes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            category,
            price,
            old_price,
            description,
            filename,
            featured,
            sizes
        ))

        connection.commit()
        connection.close()

        flash(
            "Product uploaded successfully."
        )

        return redirect(
            url_for("admin")
        )

    # --------------------------------------------------------
    # GET ADMIN DASHBOARD
    # --------------------------------------------------------

    connection = db()

    products = connection.execute("""
        SELECT *
        FROM products
        ORDER BY created_at DESC, id DESC
    """).fetchall()

    orders = connection.execute("""
        SELECT
            orders.*,
            products.name AS product_name
        FROM orders
        LEFT JOIN products
            ON orders.product_id = products.id
        ORDER BY orders.created_at DESC, orders.id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin.html",
        products=products,
        orders=orders
    )


# ============================================================
# DELETE PRODUCT
# ============================================================

@app.route(
    "/admin/delete-product/<int:product_id>",
    methods=["POST"]
)
@admin_required
def delete_product(product_id):

    connection = db()

    product_item = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    if product_item is None:

        connection.close()

        flash(
            "Product not found."
        )

        return redirect(
            url_for("admin")
        )

    # --------------------------------------------------------
    # Delete image from uploads folder
    # --------------------------------------------------------

    if product_item["image"]:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            product_item["image"]
        )

        if os.path.exists(image_path):

            try:
                os.remove(image_path)

            except OSError:
                pass

    # --------------------------------------------------------
    # Delete product
    # --------------------------------------------------------

    connection.execute("""
        DELETE FROM products
        WHERE id = ?
    """, (product_id,))

    connection.commit()
    connection.close()

    flash(
        "Product deleted successfully."
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# UPDATE ORDER STATUS
# ============================================================

@app.route(
    "/admin/order/<int:order_id>/status",
    methods=["POST"]
)
@admin_required
def update_order_status(order_id):

    status = request.form.get(
        "status",
        "Pending"
    ).strip()

    allowed_statuses = {
        "Pending",
        "Confirmed",
        "Processing",
        "Shipped",
        "Delivered",
        "Cancelled"
    }

    if status not in allowed_statuses:

        status = "Pending"

    connection = db()

    connection.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        order_id
    ))

    connection.commit()
    connection.close()

    flash(
        "Order status updated."
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# CUSTOMER SERVICE - WEBSITE API
# ============================================================

@app.route(
    "/customer-service",
    methods=["POST"]
)
def customer_service():

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        ""
    ).strip().lower()

    if not message:

        return {
            "reply":
                "Please type a message so we can help you."
        }

    # --------------------------------------------------------
    # Greetings
    # --------------------------------------------------------

    if any(
        word in message
        for word in [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening"
        ]
    ):

        reply = (
            f"Hello! Welcome to {BUSINESS_NAME}. 😊\n\n"
            "How can we help you today?"
        )

    # --------------------------------------------------------
    # Products
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "product",
            "dress",
            "wear",
            "shoe",
            "shoes",
            "bag",
            "bags",
            "jewellery",
            "jewelry",
            "accessories"
        ]
    ):

        reply = (
            "We currently offer:\n\n"
            "• Luxury Wears\n"
            "• Shoes\n"
            "• Bags\n"
            "• Jewellery & Accessories\n\n"
            "Please tell us which product you are interested in."
        )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "price",
            "cost",
            "how much"
        ]
    ):

        reply = (
            "Please tell us the name of the product "
            "you are interested in and we will help "
            "you with the price."
        )

    # --------------------------------------------------------
    # Order
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "order",
            "buy",
            "purchase"
        ]
    ):

        reply = (
            "To place an order, please provide:\n\n"
            "1. Product name\n"
            "2. Size\n"
            "3. Quantity\n"
            "4. Delivery location\n"
            "5. Phone number"
        )

    # --------------------------------------------------------
    # Delivery
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "delivery",
            "shipping",
            "deliver"
        ]
    ):

        reply = (
            "Delivery is available across Nigeria.\n\n"
            "Please send us your city or state "
            "so we can assist you with delivery information."
        )

    # --------------------------------------------------------
    # Payment
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "payment",
            "pay",
            "transfer",
            "bank"
        ]
    ):

        reply = (
            "We can assist you with payment and "
            "WhatsApp order confirmation.\n\n"
            "Please contact us on WhatsApp for payment instructions."
        )

    # --------------------------------------------------------
    # Human agent
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "human",
            "agent",
            "representative",
            "person",
            "call"
        ]
    ):

        reply = (
            f"Customer Service Phone: {PHONE_NUMBER}\n\n"
            "You can also contact us directly on WhatsApp."
        )

    # --------------------------------------------------------
    # Thank you
    # --------------------------------------------------------

    elif any(
        word in message
        for word in [
            "thanks",
            "thank you",
            "thank"
        ]
    ):

        reply = (
            "You're welcome! ❤️\n\n"
            f"Thank you for shopping with {BUSINESS_NAME}."
        )

    # --------------------------------------------------------
    # Default
    # --------------------------------------------------------

    else:

        reply = (
            f"Thank you for contacting {BUSINESS_NAME}.\n\n"
            "Please tell us whether you need help with "
            "products, prices, orders, delivery or payment."
        )

    return {
        "reply": reply
    }


# ============================================================
# WHATSAPP CUSTOMER SERVICE
# ============================================================

@app.route("/whatsapp")
def whatsapp():

    message = (
        f"Hello {BUSINESS_NAME}, "
        "I need assistance with your products."
    )

    return redirect(
        whatsapp_url(message)
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "The uploaded file is too large. "
        "Maximum size is 10 MB."
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# DEVELOPMENT SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )from tkinter import scrolledtext
from datetime import datetime
import webbrowser
import urllib.parse

# ==========================================
# RUTHELYN COLLECTIONS CUSTOMER SERVICE
# ==========================================

BUSINESS_NAME = "RUTHELYN COLLECTIONS"
PHONE_NUMBER = "08125506022"
PHONE_NUMBER = "08153984064"
WHATSAPP_NUMBER = "2348125506022"


# ==========================================
# OPEN WHATSAPP
# ==========================================

def open_whatsapp():
    message = f"Hello {BUSINESS_NAME}, I need assistance with your products."

    url = (
        f"https://wa.me/{WHATSAPP_NUMBER}"
        f"?text={urllib.parse.quote(message)}"
    )

    webbrowser.open(url)


# ==========================================
# BOT RESPONSES
# ==========================================

def get_response(message):
    msg = message.lower()

    if any(x in msg for x in ["hello", "hi", "hey"]):
        return (
            f"Hello! Welcome to {BUSINESS_NAME}. 😊\n"
            "How can we help you today?"
        )

    elif any(x in msg for x in ["product", "dress", "shoe", "bag", "jewellery"]):
        return (
            "We sell:\n"
            "• Luxury Wears\n"
            "• Shoes\n"
            "• Bags\n"
            "• Jewellery & Accessories\n\n"
            "Please tell us which item you need."
        )

    elif any(x in msg for x in ["price", "cost"]):
        return (
            "Please tell us the product name and we'll provide the price."
        )

    elif any(x in msg for x in ["order", "buy"]):
        return (
            "To place an order, tell us:\n"
            "1. Product name\n"
            "2. Size\n"
            "3. Quantity\n"
            "4. Delivery location"
        )

    elif any(x in msg for x in ["delivery", "shipping"]):
        return (
            "Delivery is available across Nigeria.\n"
            "Please send us your city or state."
        )

    elif any(x in msg for x in ["payment", "transfer"]):
        return (
            "We accept bank transfer and WhatsApp payment confirmation."
        )

    elif any(x in msg for x in ["human", "agent", "representative", "call"]):
        return (
            f"Customer Service Phone: {PHONE_NUMBER}\n\n"
            "Click the WhatsApp button below to chat with us."
        )

    elif any(x in msg for x in ["thanks", "thank you"]):
        return (
            "You're welcome! ❤️ Thank you for shopping with RUTHELYN COLLECTIONS."
        )

    else:
        return (
            "Thank you for contacting RUTHELYN COLLECTIONS.\n"
            "Please explain your request in more detail."
        )


# ==========================================
# SEND MESSAGE
# ==========================================

def send_message(event=None):

    message = user_input.get().strip()

    if message == "":
        return

    chat_area.insert(tk.END, f"\nYou: {message}\n", "customer")

    response = get_response(message)

    chat_area.insert(
        tk.END,
        f"\n{BUSINESS_NAME}: {response}\n",
        "business"
    )

    current_time = datetime.now().strftime("%I:%M %p")

    chat_area.insert(
        tk.END,
        f"{current_time}\n",
        "time"
    )

    user_input.delete(0, tk.END)
    chat_area.see(tk.END)


# ==========================================
# CLEAR CHAT
# ==========================================

def clear_chat():
    chat_area.delete("1.0", tk.END)
    welcome_message()


def welcome_message():
    chat_area.insert(
        tk.END,
        f"Welcome to {BUSINESS_NAME} Customer Service!\n\n",
        "business"
    )

    chat_area.insert(
        tk.END,
        "You can ask about products, prices, orders, delivery, or payment.\n\n"
    )

    chat_area.insert(
        tk.END,
        f"Customer Service Phone: {PHONE_NUMBER}\n\n",
        "phone"
    )


# ==========================================
# WINDOW
# ==========================================

root = tk.Tk()
root.title(f"{BUSINESS_NAME} Customer Service")
root.geometry("700x750")
root.configure(bg="#F5F5F5")

# HEADER

header = tk.Frame(root, bg="#111111", height=100)
header.pack(fill=tk.X)

tk.Label(
    header,
    text=BUSINESS_NAME,
    bg="#111111",
    fg="white",
    font=("Arial", 22, "bold")
).pack(pady=(18, 5))

tk.Label(
    header,
    text="Luxury Wears • Shoes • Bags • Jewellery",
    bg="#111111",
    fg="#D4AF37",
    font=("Arial", 11)
).pack()

# CHAT

chat_area = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    font=("Arial", 11)
)

chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

chat_area.tag_config("customer", foreground="#004AAD", font=("Arial", 11, "bold"))
chat_area.tag_config("business", foreground="#008060", font=("Arial", 11, "bold"))
chat_area.tag_config("phone", foreground="#B8860B", font=("Arial", 11, "bold"))
chat_area.tag_config("time", foreground="gray", font=("Arial", 8))

# INPUT

input_frame = tk.Frame(root, bg="#F5F5F5")
input_frame.pack(fill=tk.X, padx=10, pady=5)

user_input = tk.Entry(
    input_frame,
    font=("Arial", 12)
)

user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))

tk.Button(
    input_frame,
    text="Send",
    command=send_message,
    bg="#111111",
    fg="white",
    font=("Arial", 11, "bold"),
    width=10
).pack(side=tk.RIGHT)

# BUTTONS

button_frame = tk.Frame(root, bg="#F5F5F5")
button_frame.pack(fill=tk.X, padx=10, pady=10)

tk.Button(
    button_frame,
    text="💬 Chat on WhatsApp",
    command=open_whatsapp,
    bg="#25D366",
    fg="white",
    font=("Arial", 12, "bold"),
    pady=10
).pack(fill=tk.X)

tk.Button(
    button_frame,
    text="Clear Chat",
    command=clear_chat,
    bg="#DDDDDD",
    font=("Arial", 11),
    pady=8
).pack(fill=tk.X, pady=8)

# WELCOME MESSAGE

welcome_message()

root.bind("<Return>", send_message)

user_input.focus()

root.mainloop()

