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
from urllib.parse import quote
from werkzeug.utils import secure_filename

import sqlite3
import os
import uuid


# ============================================================
# RUTHELYN COLLECTIONS - FLASK ECOMMERCE APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# SECRET KEY
# ============================================================

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "ruthelyn-development-secret-key-change-in-render"
)


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "ruthelyn.db"
)


# ============================================================
# UPLOADS
# ============================================================

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = (
    10 * 1024 * 1024
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ============================================================
# STORE INFORMATION
# ============================================================

BUSINESS_NAME = "RUTHELYN COLLECTIONS"


WHATSAPP_NUMBER = os.environ.get(
    "WHATSAPP_NUMBER",
    "2348125506022"
)


PHONE_NUMBER = os.environ.get(
    "PHONE_NUMBER",
    "08125506022"
)


# ============================================================
# ALLOWED IMAGE TYPES
# ============================================================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db():

    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    connection = db()


    # --------------------------------------------------------
    # PRODUCTS TABLE
    # --------------------------------------------------------

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

            sold INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # --------------------------------------------------------
    # ADD SOLD COLUMN TO OLD DATABASE IF NEEDED
    # --------------------------------------------------------

    product_columns = connection.execute(
        "PRAGMA table_info(products)"
    ).fetchall()

    product_column_names = [
        row["name"]
        for row in product_columns
    ]


    if "sold" not in product_column_names:

        connection.execute("""
            ALTER TABLE products
            ADD COLUMN sold INTEGER DEFAULT 0
        """)


    # --------------------------------------------------------
    # ORDERS TABLE
    # --------------------------------------------------------

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

            FOREIGN KEY(product_id)
            REFERENCES products(id)

        )
    """)


    connection.commit()

    connection.close()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return extension in ALLOWED_EXTENSIONS


# ============================================================
# DEFAULT PRODUCT SIZES
# ============================================================

def default_sizes(category):

    if not category:
        return "One Size"

    category_lower = (
        category
        .strip()
        .lower()
    )


    if category_lower == "luxury wears":

        return "8,10,12,14"


    if category_lower == "shoes":

        return "38,39,40,41,42,43,44,45,46"


    if category_lower == "bags":

        return "One Size"


    if category_lower in {

        "jewellery & accessories",

        "jewelry & accessories",

        "jewellry & accessories"

    }:

        return "One Size"


    return "One Size"


# ============================================================
# CATEGORY NORMALIZATION
# ============================================================

def normalize_category(category):

    if not category:
        return category


    category = category.strip()


    mapping = {

        "Jewellry & Accessories":
            "Jewellery & Accessories",

        "Jewelry & Accessories":
            "Jewellery & Accessories",

        "Jewellery & Accessories":
            "Jewellery & Accessories",

        "Luxury Wear":
            "Luxury Wears",

        "Luxury Wears":
            "Luxury Wears",

        "Shoes":
            "Shoes",

        "Bags":
            "Bags"

    }


    return mapping.get(
        category,
        category
    )


# ============================================================
# WHATSAPP URL
# ============================================================

def whatsapp_url(message):

    return (
        f"https://wa.me/{WHATSAPP_NUMBER}"
        f"?text={quote(message)}"
    )


# ============================================================
# ADMIN AUTHENTICATION DECORATOR
# ============================================================

def admin_required(view_function):

    @wraps(view_function)
    def wrapped_view(
        *args,
        **kwargs
    ):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for(
                    "admin_login"
                )
            )


        return view_function(
            *args,
            **kwargs
        )


    return wrapped_view


# ============================================================
# INITIALIZE DATABASE
# ============================================================

# This runs when Gunicorn imports app.py on Render.

init_db()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    connection = db()


    # --------------------------------------------------------
    # LATEST / FEATURED PRODUCTS
    # --------------------------------------------------------

    products = connection.execute("""
        SELECT *
        FROM products

        ORDER BY
            featured DESC,
            created_at DESC,
            id DESC

        LIMIT 8
    """).fetchall()


    # --------------------------------------------------------
    # HOMEPAGE CATEGORY PRODUCTS
    # --------------------------------------------------------

    category_names = [

        "Luxury Wears",

        "Shoes",

        "Bags",

        "Jewellery & Accessories"

    ]


    category_products = {}


    for category in category_names:

        product_item = connection.execute("""
            SELECT *

            FROM products

            WHERE category = ?

            AND image IS NOT NULL

            AND image != ''

            ORDER BY
                created_at DESC,
                id DESC

            LIMIT 1
        """, (
            category,
        )).fetchone()


        category_products[
            category
        ] = product_item


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

    search = request.args.get(
        "q",
        ""
    ).strip()


    category = request.args.get(
        "category",
        ""
    ).strip()


    category = normalize_category(
        category
    )


    connection = db()


    # --------------------------------------------------------
    # SEARCH + CATEGORY
    # --------------------------------------------------------

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

            ORDER BY
                created_at DESC,
                id DESC

        """, (

            f"%{search}%",

            f"%{search}%",

            category

        )).fetchall()


    # --------------------------------------------------------
    # SEARCH ONLY
    # --------------------------------------------------------

    elif search:

        products = connection.execute("""
            SELECT *

            FROM products

            WHERE
                name LIKE ?
                OR description LIKE ?

            ORDER BY
                created_at DESC,
                id DESC

        """, (

            f"%{search}%",

            f"%{search}%"

        )).fetchall()


    # --------------------------------------------------------
    # CATEGORY ONLY
    # --------------------------------------------------------

    elif category:

        products = connection.execute("""
            SELECT *

            FROM products

            WHERE category = ?

            ORDER BY
                created_at DESC,
                id DESC

        """, (
            category,
        )).fetchall()


    # --------------------------------------------------------
    # ALL PRODUCTS
    # --------------------------------------------------------

    else:

        products = connection.execute("""
            SELECT *

            FROM products

            ORDER BY
                created_at DESC,
                id DESC
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

@app.route(
    "/product/<int:product_id>"
)
def product(product_id):

    connection = db()


    item = connection.execute("""
        SELECT *

        FROM products

        WHERE id = ?
    """, (
        product_id,
    )).fetchone()


    connection.close()


    if item is None:

        flash(
            "Product not found."
        )

        return redirect(
            url_for(
                "shop"
            )
        )


    return render_template(

        "product.html",

        product=item

    )


# ============================================================
# CHECKOUT
# ============================================================

@app.route(
    "/checkout/<int:product_id>",
    methods=[
        "GET",
        "POST"
    ]
)
def checkout(product_id):

    connection = db()


    item = connection.execute("""
        SELECT *

        FROM products

        WHERE id = ?
    """, (
        product_id,
    )).fetchone()


    connection.close()


    # --------------------------------------------------------
    # PRODUCT NOT FOUND
    # --------------------------------------------------------

    if item is None:

        flash(
            "Product not found."
        )

        return redirect(
            url_for(
                "shop"
            )
        )


    # --------------------------------------------------------
    # STOP CHECKOUT IF PRODUCT IS SOLD
    # --------------------------------------------------------

    if item["sold"]:

        flash(
            "Sorry, this product is SOLD OUT."
        )

        return redirect(

            url_for(

                "product",

                product_id=product_id

            )

        )


    # --------------------------------------------------------
    # PRODUCT SIZES
    # --------------------------------------------------------

    sizes = []


    if item["sizes"]:

        sizes = [

            size.strip()

            for size in item[
                "sizes"
            ].split(",")

            if size.strip()

        ]


    # --------------------------------------------------------
    # CHECKOUT FORM SUBMISSION
    # --------------------------------------------------------

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


        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        try:

            quantity = int(
                quantity_text
            )

            if quantity < 1:

                quantity = 1


        except ValueError:

            quantity = 1


        # ----------------------------------------------------
        # VALIDATE NAME
        # ----------------------------------------------------

        if not customer_name:

            flash(
                "Please enter your name."
            )

            return redirect(

                url_for(

                    "checkout",

                    product_id=product_id

                )

            )


        # ----------------------------------------------------
        # VALIDATE PHONE
        # ----------------------------------------------------

        if not phone:

            flash(
                "Please enter your phone number."
            )

            return redirect(

                url_for(

                    "checkout",

                    product_id=product_id

                )

            )


        # ----------------------------------------------------
        # VALIDATE ADDRESS
        # ----------------------------------------------------

        if not address:

            flash(
                "Please enter your delivery address."
            )

            return redirect(

                url_for(

                    "checkout",

                    product_id=product_id

                )

            )


        # ----------------------------------------------------
        # SAVE ORDER
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

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )

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
        # WHATSAPP CHECKOUT
        # ----------------------------------------------------

        if payment_method.lower() in {

            "pay on whatsapp",

            "whatsapp",

            "pay via whatsapp"

        }:


            total = (
                float(item["price"])
                * quantity
            )


            message = (

                f"Hello {BUSINESS_NAME},\n\n"

                f"I would like to place an order.\n\n"

                f"Order ID: #{order_id}\n"

                f"Product: {item['name']}\n"

                f"Category: {item['category']}\n"

                f"Price: ₦{float(item['price']):,.2f}\n"

                f"Quantity: {quantity}\n"

                f"Total: ₦{total:,.2f}\n"

                f"Size: {size or 'Not specified'}\n\n"

                f"Customer Name: {customer_name}\n"

                f"Phone: {phone}\n"

                f"Delivery Address: {address}\n"

            )


            return redirect(
                whatsapp_url(
                    message
                )
            )


        # ----------------------------------------------------
        # OTHER PAYMENT PAGE
        # ----------------------------------------------------

        return render_template(

            "payment.html",

            product=item,

            order_id=order_id,

            customer_name=customer_name,

            quantity=quantity,

            size=size

        )


    # --------------------------------------------------------
    # DISPLAY CHECKOUT
    # --------------------------------------------------------

    return render_template(

        "checkout.html",

        product=item,

        sizes=sizes

    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin"
            )
        )


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


        if (
            admin_username
            and admin_password
            and username == admin_username
            and password == admin_password
        ):

            session[
                "admin_logged_in"
            ] = True


            return redirect(
                url_for(
                    "admin"
                )
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

@app.route(
    "/admin/logout"
)
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )


    return redirect(
        url_for(
            "admin_login"
        )
    )


# ============================================================
# ADMIN DASHBOARD / ADD PRODUCT
# ============================================================

@app.route(
    "/admin",
    methods=[
        "GET",
        "POST"
    ]
)
@admin_required
def admin():

    # --------------------------------------------------------
    # ADD PRODUCT
    # --------------------------------------------------------

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        category = request.form.get(
            "category",
            ""
        ).strip()


        category = normalize_category(
            category
        )


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


        featured = (
            1
            if request.form.get(
                "featured"
            )
            else 0
        )


        # ----------------------------------------------------
        # VALIDATE PRODUCT NAME
        # ----------------------------------------------------

        if not name:

            flash(
                "Please enter a product name."
            )

            return redirect(
                url_for(
                    "admin"
                )
            )


        # ----------------------------------------------------
        # VALIDATE CATEGORY
        # ----------------------------------------------------

        if not category:

            flash(
                "Please select a product category."
            )

            return redirect(
                url_for(
                    "admin"
                )
            )


        # ----------------------------------------------------
        # VALIDATE PRICE
        # ----------------------------------------------------

        try:

            price = float(
                price_text
            )

            if price < 0:
                raise ValueError


        except ValueError:

            flash(
                "Please enter a valid product price."
            )

            return redirect(
                url_for(
                    "admin"
                )
            )


        # ----------------------------------------------------
        # OLD PRICE
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
        # AUTOMATIC SIZES
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
                    url_for(
                        "admin"
                    )
                )


            original_filename = secure_filename(
                image.filename
            )


            if not original_filename:

                flash(
                    "Invalid image file."
                )

                return redirect(
                    url_for(
                        "admin"
                    )
                )


            if "." not in original_filename:

                flash(
                    "Invalid image file."
                )

                return redirect(
                    url_for(
                        "admin"
                    )
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
                app.config[
                    "UPLOAD_FOLDER"
                ],
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
                    url_for(
                        "admin"
                    )
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

                sizes,

                sold

            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )

        """, (

            name,

            category,

            price,

            old_price,

            description,

            filename,

            featured,

            sizes,

            0

        ))


        connection.commit()

        connection.close()


        flash(
            "Product uploaded successfully."
        )


        return redirect(
            url_for(
                "admin"
            )
        )


    # --------------------------------------------------------
    # ADMIN DASHBOARD GET
    # --------------------------------------------------------

    connection = db()


    products = connection.execute("""
        SELECT *

        FROM products

        ORDER BY
            created_at DESC,
            id DESC
    """).fetchall()


    orders = connection.execute("""
        SELECT

            orders.*,

            products.name
            AS product_name,

            products.price
            AS product_price

        FROM orders

        LEFT JOIN products

            ON orders.product_id
            = products.id

        ORDER BY
            orders.created_at DESC,
            orders.id DESC
    """).fetchall()


    connection.close()


    return render_template(

        "admin.html",

        products=products,

        orders=orders

    )


# ============================================================
# MARK PRODUCT SOLD / AVAILABLE
# ============================================================

@app.route(
    "/admin/product/<int:product_id>/sold",
    methods=[
        "POST"
    ]
)
@admin_required
def toggle_sold(product_id):

    connection = db()


    product_item = connection.execute("""
        SELECT
            id,
            sold

        FROM products

        WHERE id = ?
    """, (
        product_id,
    )).fetchone()


    if product_item is None:

        connection.close()

        flash(
            "Product not found."
        )

        return redirect(
            url_for(
                "admin"
            )
        )


    if product_item["sold"]:

        new_status = 0

    else:

        new_status = 1


    connection.execute("""
        UPDATE products

        SET sold = ?

        WHERE id = ?
    """, (

        new_status,

        product_id

    ))


    connection.commit()

    connection.close()


    if new_status == 1:

        flash(
            "Product marked as SOLD."
        )

    else:

        flash(
            "Product marked as AVAILABLE."
        )


    return redirect(
        url_for(
            "admin"
        )
    )


# ============================================================
# DELETE PRODUCT
# ============================================================

@app.route(
    "/admin/delete-product/<int:product_id>",
    methods=[
        "POST"
    ]
)
@admin_required
def delete_product(product_id):

    connection = db()


    product_item = connection.execute("""
        SELECT *

        FROM products

        WHERE id = ?
    """, (
        product_id,
    )).fetchone()


    if product_item is None:

        connection.close()


        flash(
            "Product not found."
        )


        return redirect(
            url_for(
                "admin"
            )
        )


    # --------------------------------------------------------
    # DELETE PRODUCT IMAGE
    # --------------------------------------------------------

    if product_item["image"]:

        image_path = os.path.join(

            app.config[
                "UPLOAD_FOLDER"
            ],

            product_item[
                "image"
            ]

        )


        if os.path.exists(
            image_path
        ):

            try:

                os.remove(
                    image_path
                )

            except OSError:

                pass


    # --------------------------------------------------------
    # DELETE PRODUCT FROM DATABASE
    # --------------------------------------------------------

    connection.execute("""
        DELETE FROM products

        WHERE id = ?
    """, (
        product_id,
    ))


    connection.commit()

    connection.close()


    flash(
        "Product deleted successfully."
    )


    return redirect(
        url_for(
            "admin"
        )
    )


# ============================================================
# UPDATE ORDER STATUS
# ============================================================

@app.route(
    "/admin/order/<int:order_id>/status",
    methods=[
        "POST"
    ]
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
        url_for(
            "admin"
        )
    )


# ============================================================
# CUSTOMER SERVICE - WEBSITE CHAT API
# ============================================================

@app.route(
    "/customer-service",
    methods=[
        "POST"
    ]
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
    # GREETINGS
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
    # PRODUCTS
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
    # PRICE
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
    # ORDER
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
    # DELIVERY
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
    # PAYMENT
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
    # HUMAN AGENT
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
    # THANK YOU
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
    # DEFAULT
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

@app.route(
    "/whatsapp"
)
def whatsapp():

    message = (

        f"Hello {BUSINESS_NAME}, "

        "I need assistance with your products."

    )


    return redirect(
        whatsapp_url(
            message
        )
    )


# ============================================================
# ERROR HANDLER - 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


# ============================================================
# ERROR HANDLER - FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    flash(

        "The uploaded file is too large. "

        "Maximum size is 10 MB."

    )


    return redirect(
        url_for(
            "admin"
        )
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

    )
