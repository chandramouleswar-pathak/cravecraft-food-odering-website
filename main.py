from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional
app = FastAPI()
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")

DB_PATH = "foodhub.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            protein INTEGER NOT NULL,
            calories INTEGER NOT NULL,
            is_veg INTEGER NOT NULL,
            description TEXT,
            image_url TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            item_id INTEGER PRIMARY KEY,
            qty INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            items_json TEXT NOT NULL,
            subtotal INTEGER NOT NULL,
            delivery_fee INTEGER NOT NULL,
            total INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("SELECT COUNT(*) FROM menu_items")
    if cur.fetchone()[0] == 0:
        seed_items = [
            ("Margherita Pizza", "Pizza", 299, 18, 650, 1, "Classic cheese & tomato pizza with fresh mozzarella.", "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500&q=80"),
            ("Pepperoni Feast Pizza", "Pizza", 379, 26, 820, 0, "Loaded with spicy pepperoni and double mozzarella.", "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=500&q=80"),
            ("Classic Cheese Burger", "Burgers", 199, 16, 520, 1, "Crispy herb patty with cheddar slice and house sauce.", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500&q=80"),
            ("Double Chicken Smash Burger", "Burgers", 269, 34, 680, 0, "Juicy double grilled chicken patty with smoky mayo.", "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=500&q=80"),
            ("Hyderabadi Chicken Biryani", "Indian", 249, 32, 710, 0, "Aromatic basmati rice slow-cooked with spiced chicken & raita.", "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=500&q=80"),
            ("Paneer Tikka Masala Bowl", "Indian", 229, 24, 610, 1, "Chargrilled paneer cubes in rich tomato gravy with jeera rice.", "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=500&q=80"),
            ("Dal Makhani & Garlic Naan", "Indian", 189, 15, 590, 1, "Creamy overnight-simmered black lentils with 2 butter naans.", "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=500&q=80"),
            ("Belgian Chocolate Lava Cake", "Dessert", 149, 6, 410, 1, "Warm dark chocolate cake with a molten fudge center.", "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=500&q=80"),
            ("Cold Coffee Frappe", "Drinks", 119, 5, 240, 1, "Chilled espresso blended with creamy milk and ice.", "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=500&q=80"),
            ("Mango Mint Cooler", "Drinks", 99, 1, 140, 1, "Refreshing Alphonso mango fizz with crushed mint leaves.", "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=500&q=80")
        ]
        cur.executemany("""
            INSERT INTO menu_items (name, category, price, protein, calories, is_veg, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_items)

        sample_orders = [
            ("FH1023", "Aman Verma", "9876543210", "Hostel Block B, Room 204", "UPI", json.dumps([{"name": "Margherita Pizza", "qty": 1, "price": 299}]), 299, 40, 339, "Delivered", "10:15 AM"),
            ("FH1024", "Priya Nair", "9823456781", "Civil Lines, Sector 4", "Cash on Delivery", json.dumps([{"name": "Hyderabadi Chicken Biryani", "qty": 2, "price": 249}]), 498, 40, 538, "Out for delivery", "11:05 AM")
        ]
        cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_orders)

    conn.commit()
    conn.close()

init_db()

def get_cart_details(conn):
    rows = conn.execute("""
        SELECT m.*, c.qty, (m.price * c.qty) as line_total
        FROM cart c JOIN menu_items m ON c.item_id = m.id
    """).fetchall()
    items = [dict(r) for r in rows]
    subtotal = sum(i["line_total"] for i in items)
    delivery = 40 if subtotal > 0 else 0
    total = subtotal + delivery
    count = sum(i["qty"] for i in items)
    return {"items": items, "subtotal": subtotal, "delivery": delivery, "total": total, "count": count}

def find_smart_combo(conn, max_budget: int, min_protein: int, veg_only: bool):
    query = "SELECT * FROM menu_items"
    if veg_only:
        query += " WHERE is_veg = 1"
    items = [dict(r) for r in conn.execute(query).fetchall()]
    best_combo = []
    best_score = -1

    for i in range(len(items)):
        if items[i]["price"] <= max_budget and items[i]["protein"] >= min_protein:
            score = items[i]["protein"] * 2 - (items[i]["price"] * 0.05)
            if score > best_score:
                best_score = score
                best_combo = [items[i]]
        for j in range(i + 1, len(items)):
            tp = items[i]["price"] + items[j]["price"]
            tprot = items[i]["protein"] + items[j]["protein"]
            if tp <= max_budget and tprot >= min_protein:
                score = tprot * 2 - (tp * 0.05)
                if score > best_score:
                    best_score = score
                    best_combo = [items[i], items[j]]
    return best_combo

@app.get("/", response_class=HTMLResponse)
def main_view(
    request: Request,
    screen: str = "home",
    category: str = "All",
    search: str = "",
    veg_only: int = 0,
    item_id: Optional[int] = None,
    order_id: Optional[str] = None,
    max_budget: Optional[int] = None,
    min_protein: Optional[int] = None,
    combo_veg: int = 0
):
    conn = get_db()
    cart = get_cart_details(conn)

    # Menu query
    menu_query = "SELECT * FROM menu_items WHERE 1=1"
    params = []
    if category != "All":
        menu_query += " AND category = ?"
        params.append(category)
    if search.strip():
        menu_query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
    if veg_only == 1:
        menu_query += " AND is_veg = 1"
    menu_items = [dict(r) for r in conn.execute(menu_query, params).fetchall()]

    # Selected item for Screen 3 (Food Details)
    selected_item = None
    if item_id:
        row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        if row:
            selected_item = dict(row)

    # Smart Combo result
    smart_combo = None
    if max_budget is not None and min_protein is not None:
        smart_combo = find_smart_combo(conn, max_budget, min_protein, bool(combo_veg))

    # Orders & Admin Stats
    orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY rowid DESC").fetchall()]
    for o in orders:
        o["items"] = json.loads(o["items_json"])

    tracked_order = None
    if order_id:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id.strip().upper(),)).fetchone()
        if row:
            tracked_order = dict(row)
            tracked_order["items"] = json.loads(tracked_order["items_json"])
    elif orders:
        tracked_order = orders[0]

    total_revenue = sum(o["total"] for o in orders)
    unique_customers = len(set(o["phone"] for o in orders))
    total_menu_count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]

    conn.close()
    return templates.TemplateResponse(request,"index.html", {
        "request": request,
        "screen": screen,
        "category": category,
        "search": search,
        "veg_only": veg_only,
        "menu_items": menu_items,
        "selected_item": selected_item,
        "cart": cart,
        "smart_combo": smart_combo,
        "max_budget": max_budget or 400,
        "min_protein": min_protein or 25,
        "combo_veg": combo_veg,
        "orders": orders,
        "tracked_order": tracked_order,
        "stats": {
            "orders": len(orders),
            "revenue": total_revenue,
            "customers": unique_customers,
            "menu_items": total_menu_count
        }
    })

@app.post("/cart/add")
def add_to_cart(item_id: int = Form(...), qty: int = Form(1), redirect_to: str = Form("menu")):
    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute("SELECT qty FROM cart WHERE item_id = ?", (item_id,)).fetchone()
    if existing:
        cur.execute("UPDATE cart SET qty = qty + ? WHERE item_id = ?", (qty, item_id))
    else:
        cur.execute("INSERT INTO cart (item_id, qty) VALUES (?, ?)", (item_id, qty))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?screen={redirect_to}", status_code=303)

@app.post("/cart/add-combo")
def add_combo_to_cart(item_ids: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    for raw_id in item_ids.split(","):
        if raw_id.strip().isdigit():
            iid = int(raw_id.strip())
            existing = cur.execute("SELECT qty FROM cart WHERE item_id = ?", (iid,)).fetchone()
            if existing:
                cur.execute("UPDATE cart SET qty = qty + 1 WHERE item_id = ?", (iid,))
            else:
                cur.execute("INSERT INTO cart (item_id, qty) VALUES (?, 1)", (iid,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/?screen=cart", status_code=303)

@app.post("/cart/update")
def update_cart(item_id: int = Form(...), delta: int = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT qty FROM cart WHERE item_id = ?", (item_id,)).fetchone()
    if row:
        new_qty = row["qty"] + delta
        if new_qty <= 0:
            cur.execute("DELETE FROM cart WHERE item_id = ?", (item_id,))
        else:
            cur.execute("UPDATE cart SET qty = ? WHERE item_id = ?", (new_qty, item_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/?screen=cart", status_code=303)

@app.post("/checkout")
def place_order(
    customer_name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    payment_method: str = Form("Cash on Delivery")
):
    conn = get_db()
    cart = get_cart_details(conn)
    if not cart["items"]:
        conn.close()
        return RedirectResponse(url="/?screen=menu", status_code=303)

    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    order_id = f"FH{1025 + count}"
    now_str = datetime.now().strftime("%I:%M %p")

    order_items = [{"name": i["name"], "qty": i["qty"], "price": i["price"]} for i in cart["items"]]
    cur.execute("""
        INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, customer_name.strip(), phone.strip(), address.strip(),
        payment_method, json.dumps(order_items),
        cart["subtotal"], cart["delivery"], cart["total"],
        "Preparing", now_str
    ))
    cur.execute("DELETE FROM cart")
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/?screen=track&order_id={order_id}", status_code=303)

@app.post("/admin/status")
def update_order_status(order_id: str = Form(...), status: str = Form(...)):
    conn = get_db()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/?screen=admin", status_code=303)