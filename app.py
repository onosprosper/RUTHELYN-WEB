from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    Response,
    send_from_directory,
)

from functools import wraps
from urllib.parse import quote, urlparse, unquote
from werkzeug.utils import secure_filename

import psycopg
from psycopg.rows import dict_row
import cloudinary
import cloudinary.uploader
import cloudinary.utils
import os
import uuid
import json
from datetime import datetime, timezone


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

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured.")


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
# SITE / SEO INFORMATION
# ============================================================

SITE_URL = os.environ.get(
    "SITE_URL",
    "https://ruthelyncollect.onrender.com"
).rstrip("/")

DEFAULT_SEO_TITLE = (
    "RUTHELYN COLLECTIONS | Women's Fashion in Nigeria"
)

DEFAULT_SEO_DESCRIPTION = (
    "Shop elegant women's fashion, luxury wears, shoes, bags and "
    "accessories from RUTHELYN COLLECTIONS. Delivery available in "
    "Lagos, Abuja, Port Harcourt and across Nigeria."
)

TARGET_CITIES = [
    "Lagos",
    "Abuja",
    "Port Harcourt"
]


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
# DATABASE CONNECTION / INITIALIZATION
# ============================================================

class DatabaseConnection:
    """Small compatibility wrapper so existing SQLite-style ? placeholders work with PostgreSQL."""

    def __init__(self):
        self.connection = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row
        )

    def execute(self, query, params=None):
        postgres_query = query.replace("?", "%s")
        return self.connection.execute(
            postgres_query,
            params or ()
        )

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def db():
    return DatabaseConnection()


def init_db():
    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            old_price DOUBLE PRECISION,
            description TEXT,
            image TEXT,
            featured INTEGER DEFAULT 0,
            sizes TEXT,
            sold INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id BIGSERIAL PRIMARY KEY,
            product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            size TEXT,
            quantity INTEGER DEFAULT 1,
            payment_method TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
# CLOUDINARY IMAGE HELPERS
# ============================================================

CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()

if not CLOUDINARY_URL:
    raise RuntimeError("CLOUDINARY_URL is not configured.")

_cloudinary_parts = urlparse(CLOUDINARY_URL)

if (
    _cloudinary_parts.scheme != "cloudinary"
    or not _cloudinary_parts.hostname
    or not _cloudinary_parts.username
    or not _cloudinary_parts.password
):
    raise RuntimeError("CLOUDINARY_URL is not valid.")

cloudinary.config(
    cloud_name=_cloudinary_parts.hostname,
    api_key=unquote(_cloudinary_parts.username),
    api_secret=unquote(_cloudinary_parts.password),
    secure=True
)


def upload_product_image(file_object, public_id=None):
    options = {
        "folder": "ruthelyn_products",
        "resource_type": "image",
        "overwrite": False
    }

    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True

    result = cloudinary.uploader.upload(
        file_object,
        **options
    )

    return result["public_id"]


def delete_product_image(image_value):
    if not image_value:
        return

    image_value = str(image_value).strip()

    # Old local filenames are not Cloudinary public IDs.
    if image_value.startswith(("http://", "https://")):
        return

    try:
        cloudinary.uploader.destroy(
            image_value,
            invalidate=True,
            resource_type="image"
        )
    except Exception:
        pass


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
# SEO HELPERS
# ============================================================

def absolute_url(path="/"):
    if not path.startswith("/"):
        path = "/" + path
    return SITE_URL + path


def product_image_url(item):
    if item and item["image"]:
        image_value = str(item["image"]).strip()
        if image_value.startswith(("http://", "https://")):
            return image_value
        return cloudinary.CloudinaryImage(
            image_value
        ).build_url(secure=True)

    return absolute_url(
        url_for("static", filename="logo.jpg")
    )


def product_image_src(image_value):
    if not image_value:
        return url_for("static", filename="logo.jpg")

    image_value = str(image_value).strip()
    if image_value.startswith(("http://", "https://")):
        return image_value

    return cloudinary.CloudinaryImage(
        image_value
    ).build_url(secure=True)


def static_with_cloudinary(filename):
    if filename.startswith("uploads/"):
        public_id = filename[len("uploads/"):].strip("/")
        if public_id:
            return redirect(
                cloudinary.CloudinaryImage(public_id).build_url(secure=True),
                code=302
            )

    return send_from_directory(
        app.static_folder,
        filename
    )


# Existing templates already use url_for('static', filename='uploads/...').
# Keep those templates working while product images live permanently on Cloudinary.
app.view_functions["static"] = static_with_cloudinary


def build_product_schema(item):
    availability = (
        "https://schema.org/OutOfStock"
        if item["sold"]
        else "https://schema.org/InStock"
    )

    description = (
        item["description"].strip()
        if item["description"]
        else f"Shop {item['name']} from {BUSINESS_NAME} in Nigeria."
    )

    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": item["name"],
        "description": description,
        "image": [product_image_url(item)],
        "sku": f"RUT-{item['id']}",
        "brand": {
            "@type": "Brand",
            "name": BUSINESS_NAME
        },
        "offers": {
            "@type": "Offer",
            "url": absolute_url(
                url_for("product", product_id=item["id"])
            ),
            "priceCurrency": "NGN",
            "price": f"{float(item['price']):.2f}",
            "availability": availability,
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {
                "@type": "Organization",
                "name": BUSINESS_NAME
            }
        }
    }


@app.context_processor
def inject_store_context():
    return {
        "business_name": BUSINESS_NAME,
        "site_url": SITE_URL,
        "whatsapp_number": WHATSAPP_NUMBER,
        "phone_number": PHONE_NUMBER,
        "default_seo_title": DEFAULT_SEO_TITLE,
        "default_seo_description": DEFAULT_SEO_DESCRIPTION,
        "target_cities": TARGET_CITIES,
        "product_image_src": product_image_src
    }

# ================================
# CUSTOMER TRUST PAGES
# ================================

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/delivery")
def delivery():
    return render_template("delivery.html")


@app.route("/returns")
def returns():
    return render_template("returns.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")
    
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

        category_products=category_products,

        seo_title=DEFAULT_SEO_TITLE,

        seo_description=DEFAULT_SEO_DESCRIPTION,

        canonical_url=absolute_url("/")

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

        search=search,

        seo_title=(
            f"{category} in Nigeria | {BUSINESS_NAME}"
            if category
            else f"Shop Women's Fashion in Nigeria | {BUSINESS_NAME}"
        ),

        seo_description=(
            f"Shop {category.lower()} from {BUSINESS_NAME}. Delivery in Lagos, "
            "Abuja, Port Harcourt and nationwide across Nigeria."
            if category
            else DEFAULT_SEO_DESCRIPTION
        ),

        canonical_url=absolute_url(
            url_for("shop", category=category)
            if category
            else url_for("shop")
        )

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

    # --------------------------------------------------------
    # PRODUCT NOT FOUND
    # --------------------------------------------------------

    if item is None:

        flash(
            "Product not found."
        )

        return redirect(
            url_for("shop")
        )

    # --------------------------------------------------------
    # PRODUCT SIZES
    # --------------------------------------------------------

    sizes = []

    if item["sizes"]:

        sizes = [
            size.strip()
            for size in item["sizes"].split(",")
            if size.strip()
        ]

    # --------------------------------------------------------
    # DISPLAY PRODUCT
    # --------------------------------------------------------

    return render_template(
        "product.html",
        product=item,
        sizes=sizes,
        seo_title=f"{item['name']} | Buy Online in Nigeria | {BUSINESS_NAME}",
        seo_description=(
            (item["description"] or "").strip()
            or f"Buy {item['name']} from {BUSINESS_NAME}. Delivery available in Lagos, Abuja, Port Harcourt and across Nigeria."
        ),
        canonical_url=absolute_url(
            url_for("product", product_id=item["id"])
        ),
        product_image_url=product_image_url(item),
        product_schema=json.dumps(
            build_product_schema(item),
            ensure_ascii=False
        )
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
            RETURNING id

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


        order_row = cursor.fetchone()
        order_id = order_row["id"]


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


            try:
                filename = upload_product_image(
                    image
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
# EDIT PRODUCT
# ============================================================

@app.route(
    "/admin/product/<int:product_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):

    connection = db()

    product_item = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (product_id,)).fetchone()

    # Product does not exist
    if product_item is None:
        connection.close()
        flash("Product not found.")
        return redirect(url_for("admin"))

    # ========================================================
    # SAVE EDITED PRODUCT
    # ========================================================

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        category = normalize_category(
            request.form.get(
                "category", ""
            ).strip()
        )

        price_text = request.form.get(
            "price", ""
        ).strip()

        old_price_text = request.form.get(
            "old_price", ""
        ).strip()

        sizes = request.form.get(
            "sizes", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        featured = (
            1
            if request.form.get("featured")
            else 0
        )

        sold = (
            1
            if request.form.get("sold")
            else 0
        )

        # ----------------------------------------
        # PRODUCT NAME
        # ----------------------------------------

        if not name:
            connection.close()

            flash(
                "Please enter a product name."
            )

            return redirect(
                url_for(
                    "edit_product",
                    product_id=product_id
                )
            )

        # ----------------------------------------
        # CATEGORY
        # ----------------------------------------

        if not category:
            connection.close()

            flash(
                "Please select a category."
            )

            return redirect(
                url_for(
                    "edit_product",
                    product_id=product_id
                )
            )

        # ----------------------------------------
        # PRICE
        # ----------------------------------------

        try:
            price = float(price_text)

            if price < 0:
                raise ValueError

        except ValueError:

            connection.close()

            flash(
                "Please enter a valid price."
            )

            return redirect(
                url_for(
                    "edit_product",
                    product_id=product_id
                )
            )

        # ----------------------------------------
        # OLD PRICE
        # ----------------------------------------

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

        # ----------------------------------------
        # SIZES
        # ----------------------------------------

        if not sizes:
            sizes = default_sizes(
                category
            )

        # ----------------------------------------
        # CURRENT IMAGE
        # ----------------------------------------

        filename = product_item["image"]

        # ----------------------------------------
        # NEW IMAGE
        # ----------------------------------------

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            if not allowed(image.filename):

                connection.close()

                flash(
                    "Invalid image format. "
                    "Use PNG, JPG, JPEG or WEBP."
                )

                return redirect(
                    url_for(
                        "edit_product",
                        product_id=product_id
                    )
                )

            original_filename = (
                secure_filename(
                    image.filename
                )
            )

            if (
                not original_filename
                or "." not in original_filename
            ):

                connection.close()

                flash(
                    "Invalid image file."
                )

                return redirect(
                    url_for(
                        "edit_product",
                        product_id=product_id
                    )
                )

            try:
                new_filename = upload_product_image(
                    image
                )
            except Exception:
                connection.close()
                flash(
                    "There was a problem uploading the image."
                )
                return redirect(
                    url_for(
                        "edit_product",
                        product_id=product_id
                    )
                )

            delete_product_image(filename)
            filename = new_filename

        # ----------------------------------------
        # UPDATE DATABASE
        # ----------------------------------------

        connection.execute("""
            UPDATE products
            SET
                name = ?,
                category = ?,
                price = ?,
                old_price = ?,
                description = ?,
                image = ?,
                featured = ?,
                sizes = ?,
                sold = ?
            WHERE id = ?
        """, (
            name,
            category,
            price,
            old_price,
            description,
            filename,
            featured,
            sizes,
            sold,
            product_id
        ))

        connection.commit()
        connection.close()

        flash(
            "Product updated successfully."
        )

        return redirect(
            url_for("admin")
        )

    # ========================================================
    # SHOW EDIT PAGE
    # ========================================================

    connection.close()

    return render_template(
        "edit_product.html",
        product=product_item
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
    # DELETE PRODUCT IMAGE FROM CLOUDINARY
    # --------------------------------------------------------

    delete_product_image(
        product_item["image"]
    )


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
# SEO: SITEMAP.XML
# ============================================================

@app.route("/sitemap.xml")
def sitemap():
    connection = db()
    products = connection.execute("""
        SELECT id, created_at
        FROM products
        ORDER BY id DESC
    """).fetchall()
    connection.close()

    urls = [
        (absolute_url("/"), None, "1.0", "daily"),
        (absolute_url("/shop"), None, "0.9", "daily"),
    ]

    for category in [
        "Luxury Wears",
        "Shoes",
        "Bags",
        "Jewellery & Accessories"
    ]:
        urls.append((
            absolute_url(url_for("shop", category=category)),
            None,
            "0.8",
            "daily"
        ))

    for item in products:
        lastmod = None
        if item["created_at"]:
            try:
                lastmod = str(item["created_at"]).split(" ")[0]
            except Exception:
                lastmod = None

        urls.append((
            absolute_url(
                url_for("product", product_id=item["id"])
            ),
            lastmod,
            "0.8",
            "weekly"
        ))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for loc, lastmod, priority, changefreq in urls:
        parts.append("<url>")
        parts.append(f"<loc>{loc}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod}</lastmod>")
        parts.append(f"<changefreq>{changefreq}</changefreq>")
        parts.append(f"<priority>{priority}</priority>")
        parts.append("</url>")

    parts.append("</urlset>")

    return Response(
        "\n".join(parts),
        mimetype="application/xml"
    )


# ============================================================
# SEO: ROBOTS.TXT
# ============================================================

@app.route("/robots.txt")
def robots():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /checkout/\n"
        f"Sitemap: {absolute_url('/sitemap.xml')}\n"
    )

    return Response(
        content,
        mimetype="text/plain"
    )


# ============================================================
# PRODUCT-SPECIFIC WHATSAPP ORDER LINK
# ============================================================

@app.route("/whatsapp/product/<int:product_id>")
def whatsapp_product(product_id):
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

    message = (
        f"Hello {BUSINESS_NAME},\n\n"
        f"I am interested in this product:\n"
        f"Product: {item['name']}\n"
        f"Price: ₦{float(item['price']):,.0f}\n"
        f"Product link: {absolute_url(url_for('product', product_id=item['id']))}\n\n"
        "Please confirm availability, size and delivery cost to my location."
    )

    return redirect(whatsapp_url(message))


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
# BASIC SECURITY / CRAWLING HEADERS
# ============================================================

@app.after_request
def add_response_headers(response):
    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff"
    )
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin"
    )

    # Keep private/admin and checkout pages out of search engines.
    if request.path.startswith("/admin") or request.path.startswith("/checkout"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response




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
