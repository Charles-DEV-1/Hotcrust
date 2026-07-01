import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote_plus

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MENU_FILE = DATA_DIR / "menu.json"
DATABASE = DATA_DIR / "menu.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "2349169036334")
MENU_CARD_PRICES = [
    "₦3,500",
    "₦4,200",
    "₦5,000",
    "₦2,800",
    "₦6,000",
    "₦3,900",
    "₦7,200",
    "₦4,500",
    "₦4,800",
    "₦5,300",
    "₦6,400",
    "₦5,900",
]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-hotcrust-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def ensure_storage():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not MENU_FILE.exists():
        MENU_FILE.write_text("[]", encoding="utf-8")


def get_db_connection():
    ensure_storage()
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    ensure_storage()
    if not DATABASE.exists():
        conn = get_db_connection()
        conn.execute(
            """
            CREATE TABLE menu_items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                image TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()


def migrate_json_to_sqlite():
    ensure_storage()
    if not MENU_FILE.exists():
        return

    try:
        with MENU_FILE.open("r", encoding="utf-8") as menu_file:
            menu_items = json.load(menu_file)
    except Exception:
        menu_items = []

    if not menu_items:
        return

    conn = get_db_connection()
    existing_count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    if existing_count == 0:
        conn.executemany(
            "INSERT INTO menu_items (id, name, description, price, image) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    item.get("id", uuid4().hex),
                    item.get("name", ""),
                    item.get("description", ""),
                    item.get("price", ""),
                    item.get("image", ""),
                )
                for item in menu_items
            ],
        )
        conn.commit()
    conn.close()


def load_menu_items():
    initialize_database()
    migrate_json_to_sqlite()
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM menu_items ORDER BY rowid ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_menu_items(items):
    initialize_database()
    conn = get_db_connection()
    conn.execute("DELETE FROM menu_items")
    conn.executemany(
        "INSERT INTO menu_items (id, name, description, price, image) VALUES (?, ?, ?, ?, ?)",
        [
            (
                item.get("id", uuid4().hex),
                item.get("name", ""),
                item.get("description", ""),
                item.get("price", ""),
                item.get("image", ""),
            )
            for item in items
        ],
    )
    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def list_menu_images():
    images = []
    seen = set()

    # helper to process a file path and add metadata
    def add_image(path, index, prefix=""):
        if not path.is_file() or path.suffix.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
            return

        raw_name = path.stem
        if raw_name.lower().startswith("whatsapp image"):
            item_name = f"Hot Crust Special {index + 1}"
        else:
            item_name = raw_name.replace("-", " ").replace("_", " ").title()

        price = MENU_CARD_PRICES[index % len(MENU_CARD_PRICES)]
        order_text = quote_plus(f"Hello, I want to buy {item_name} for {price}")

        filename = (prefix + path.name) if prefix else path.name
        # avoid duplicates
        if filename in seen:
            return
        seen.add(filename)

        images.append(
            {
                "id": filename,
                "name": item_name,
                "image": url_for("static", filename=(f"{prefix}{path.name}" if prefix else path.name)),
                "price": price,
                "order_url": f"https://wa.me/{WHATSAPP_NUMBER}?text={order_text}",
            }
        )

    static_dir = BASE_DIR / "static"
    # scan root static files first
    file_paths = sorted(static_dir.glob("*"), key=lambda path: path.name)
    for index, image_path in enumerate(file_paths):
        add_image(image_path, index)

    # then scan uploads folder (ensure uploaded items appear too)
    try:
        upload_files = sorted(UPLOAD_DIR.glob("*"), key=lambda path: path.name)
        base_index = len(file_paths)
        for i, upload_path in enumerate(upload_files):
            add_image(upload_path, base_index + i, prefix="uploads/")
    except Exception:
        pass

    return images


def admin_is_logged_in():
    return session.get("admin_logged_in") is True


@app.route("/")
def home():
    return render_template("index.html", menu_items=load_menu_items())


@app.route("/menu")
def menu_page():
    # show both stored menu items (from JSON) and discovered static/upload images
    menu_items = load_menu_items()
    # build a set of image ids already used by stored menu items to avoid duplicates
    existing_ids = set()
    for it in menu_items:
        img = it.get("image", "")
        if img:
            tail = img.rsplit("/", 1)[-1]
            existing_ids.add(tail)
            existing_ids.add(f"uploads/{tail}")

    return render_template(
        "menu.html",
        menu_items=menu_items,
        menu_images=list_menu_images(),
        existing_image_ids=existing_ids,
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("action") == "login":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        expected_password = os.environ.get("ADMIN_PASSWORD", "hotcrust2026")

        if username == "admin" and password == expected_password:
            session["admin_logged_in"] = True
            flash("Welcome back. You can now update the menu.", "success")
            return redirect(url_for("admin"))

        flash("Incorrect admin login details.", "error")

    if not admin_is_logged_in():
        return render_template("admin.html", menu_items=[], static_images=[], logged_in=False)

    # pass both stored menu items and all static images so admin can see everything
    return render_template(
        "admin.html",
        menu_items=load_menu_items(),
        static_images=list_menu_images(),
        logged_in=True,
    )


@app.route("/admin/menu/add", methods=["POST"])
def add_menu_item():
    if not admin_is_logged_in():
        return redirect(url_for("admin"))

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "").strip()
    image = request.files.get("image")

    if not name or not description or not price or not image or image.filename == "":
        flash("Please add a name, description, price, and image.", "error")
        return redirect(url_for("admin"))

    if not allowed_file(image.filename):
        flash("Use a PNG, JPG, JPEG, GIF, or WEBP image.", "error")
        return redirect(url_for("admin"))

    original_name = secure_filename(image.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    image.save(app.config["UPLOAD_FOLDER"] / filename)

    menu_items = load_menu_items()
    menu_items.append(
        {
            "id": uuid4().hex,
            "name": name,
            "description": description,
            "price": price,
            "image": url_for("static", filename=f"uploads/{filename}"),
        }
    )
    save_menu_items(menu_items)

    flash(f"{name} has been added to the website menu.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/menu/<item_id>/delete", methods=["POST"])
def delete_menu_item(item_id):
    if not admin_is_logged_in():
        return redirect(url_for("admin"))

    menu_items = load_menu_items()
    updated_items = [item for item in menu_items if item.get("id") != item_id]
    save_menu_items(updated_items)
    # attempt to remove uploaded image file if it belongs to uploads
    try:
        # find the removed item to get its image path
        removed = next((it for it in menu_items if it.get("id") == item_id), None)
        if removed:
            image_url = removed.get("image", "")
            if "/uploads/" in image_url:
                filename = image_url.rsplit("/uploads/", 1)[-1]
                file_path = UPLOAD_DIR / filename
                if file_path.exists():
                    file_path.unlink()
    except Exception:
        pass

    flash("Menu item removed.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/menu/<item_id>/edit", methods=["POST"])
def edit_menu_item(item_id):
    if not admin_is_logged_in():
        return redirect(url_for("admin"))

    menu_items = load_menu_items()
    changed = False
    for item in menu_items:
        if item.get("id") == item_id:
            item["name"] = request.form.get("name", item.get("name", "")).strip()
            item["description"] = request.form.get("description", item.get("description", "")).strip()
            item["price"] = request.form.get("price", item.get("price", "")).strip()
            changed = True
            break

    if changed:
        save_menu_items(menu_items)
        flash("Menu item updated.", "success")
    else:
        flash("Menu item not found.", "error")

    return redirect(url_for("admin"))


@app.route("/admin/static/delete", methods=["POST"])
def delete_static_image():
    if not admin_is_logged_in():
        return redirect(url_for("admin"))

    filename = request.form.get("filename", "").strip()
    if not filename:
        flash("No filename provided.", "error")
        return redirect(url_for("admin"))

    # ensure filename does not traverse directories
    if ".." in filename or filename.startswith("/"):
        flash("Invalid filename.", "error")
        return redirect(url_for("admin"))

    file_path = BASE_DIR / "static" / filename
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
            flash(f"Removed static file {filename}.", "success")
        except Exception:
            flash("Failed to remove file.", "error")
    else:
        flash("File not found.", "error")

    return redirect(url_for("admin"))


@app.route("/admin/menu/import", methods=["POST"])
def import_static_images():
    if not admin_is_logged_in():
        return redirect(url_for("admin"))

    menu_items = load_menu_items()
    existing_files = { (it.get("image", "").rsplit('/', 1)[-1]) for it in menu_items }

    discovered = list_menu_images()
    added = 0
    for img in discovered:
        # img['id'] is filename or uploads/filename
        # normalize to tail
        tail = img["id"].split("/", 1)[-1]
        if tail in existing_files:
            continue
        # create a new menu item
        menu_items.append(
            {
                "id": uuid4().hex,
                "name": img.get("name", tail),
                "description": "Imported from static folder.",
                "price": img.get("price", ""),
                "image": img.get("image"),
            }
        )
        added += 1

    if added:
        save_menu_items(menu_items)
        flash(f"Imported {added} images into menu.", "success")
    else:
        flash("No new images to import.", "muted")

    return redirect(url_for("admin"))


@app.route("/admin/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    ensure_storage()
    initialize_database()
    migrate_json_to_sqlite()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"},
    )
