from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sqlite3, os, uuid, urllib.parse
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "temporary-ruthelyn-secret-key"
)
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

WHATSAPP_NUMBER = "2348125506022"
ALLOWED_EXTENSIONS = {"png","jpg","jpeg","webp"}

def db():
    conn = sqlite3.connect(os.path.join(app.root_path, "ruthelyn.db"))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn=db()
    conn.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        category TEXT NOT NULL, price REAL NOT NULL, old_price REAL,
        description TEXT, image TEXT, featured INTEGER DEFAULT 0,
        sizes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cols=[r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
    if "sizes" not in cols: conn.execute("ALTER TABLE products ADD COLUMN sizes TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
        customer_name TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL,
        size TEXT, quantity INTEGER DEFAULT 1, amount REAL NOT NULL,
        payment_method TEXT, payment_status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close()

def allowed(f): return "." in f and f.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS
def default_sizes(c):
    if c=="Luxury Wears": return "8,10,12,14"
    if c=="Shoes": return "38,39,40,41,42,43,44,45,46"
    return ""

@app.route("/")
def home():
    conn=db(); products=conn.execute("SELECT * FROM products ORDER BY featured DESC, created_at DESC LIMIT 8").fetchall(); conn.close()
    return render_template("index.html",products=products)

@app.route("/shop")
def shop():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM products"
    clauses, params = [], []
    if q:
        clauses.append("(name LIKE ? OR description LIKE ? OR category LIKE ?)")
        term = f"%{q}%"
        params += [term, term, term]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY featured DESC, created_at DESC"
    conn=db(); products=conn.execute(sql, params).fetchall(); conn.close()
    return render_template("shop.html",products=products,search=q,category=category)

@app.route("/product/<int:product_id>")
def product(product_id):
    conn=db(); item=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone(); conn.close()
    if not item: return redirect(url_for("shop"))
    sizes=[x.strip() for x in (item["sizes"] or "").split(",") if x.strip()]
    return render_template("product.html",product=item,sizes=sizes)

@app.post("/checkout/<int:product_id>")
def checkout(product_id):
    conn=db(); product=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone()
    if not product: conn.close(); return redirect(url_for("shop"))
    name=request.form["customer_name"]; phone=request.form["phone"]; address=request.form["address"]
    size=request.form.get("size",""); quantity=max(1,int(request.form.get("quantity",1)))
    method=request.form.get("payment_method","Pay on WhatsApp"); amount=float(product["price"])*quantity
    conn.execute("""INSERT INTO orders(product_id,customer_name,phone,address,size,quantity,amount,payment_method)
                    VALUES(?,?,?,?,?,?,?,?)""",(product_id,name,phone,address,size,quantity,amount,method))
    conn.commit(); conn.close()
    if method=="Pay on WhatsApp":
        msg=f"Hello RUTHELYN COLLECTIONS, I want to order {product['name']}. Size: {size}. Quantity: {quantity}. Total: ₦{amount:,.0f}. Name: {name}. Phone: {phone}. Address: {address}."
        return redirect("https://wa.me/"+WHATSAPP_NUMBER+"?text="+urllib.parse.quote(msg))
    return render_template("payment.html",product=product,amount=amount,customer_name=name,size=size,quantity=quantity,payment_method=method)

@app.route("/admin",methods=["GET","POST"])
# =========================================================
# ADMIN LOGIN PROTECTION
# =========================================================

def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)

    return wrapped_view


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if (
            username == admin_username
            and password == admin_password
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))

        flash("Invalid username or password.")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)

    return redirect(url_for("admin_login"))
def admin():
    if request.method=="POST":
        image=request.files.get("image"); filename=None
        if image and image.filename and allowed(image.filename):
            ext=image.filename.rsplit(".",1)[1].lower(); filename=f"{uuid.uuid4().hex}.{ext}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
        c=request.form["category"]; sizes=request.form.get("sizes","").strip() or default_sizes(c)
        conn=db(); conn.execute("""INSERT INTO products(name,category,price,old_price,description,image,featured,sizes)
        VALUES(?,?,?,?,?,?,?,?)""",(request.form["name"],c,request.form["price"],request.form.get("old_price") or None,request.form.get("description",""),filename,1 if request.form.get("featured") else 0,sizes)); conn.commit(); conn.close()
        return redirect(url_for("admin"))
    conn=db(); products=conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    orders=conn.execute("SELECT orders.*,products.name product_name FROM orders LEFT JOIN products ON orders.product_id=products.id ORDER BY orders.created_at DESC").fetchall(); conn.close()
    return render_template("admin.html",products=products,orders=orders)

# Initialise database when the application starts
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
