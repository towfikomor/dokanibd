import sqlite3
import hashlib
import datetime

class ECommerceModel:
    def __init__(self, db_name="ecommerce.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        conn = self.get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'customer' -- 'customer' or 'admin'
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                image_url TEXT,
                category_id INTEGER,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total_amount REAL NOT NULL,
                payment_method TEXT NOT NULL, -- 'COD' or 'bKash'
                payment_status TEXT DEFAULT 'Pending', -- 'Pending', 'Paid', 'Failed'
                order_status TEXT DEFAULT 'Processing', -- 'Processing', 'Shipped', 'Delivered', 'Cancelled'
                bkash_trx_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        
        # Seed default admin and settings if not exist
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cur.fetchone()[0] == 0:
            hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
            cur.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                        ("Dokanibd Admin", "admin@dokanibd.com", hashed_pw, "admin"))
            conn.commit()

        cur.execute("SELECT COUNT(*) FROM settings WHERE key = 'bkash_enabled'")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", [
                ("bkash_enabled", "true"),
                ("bkash_merchant_number", "01700000000")
            ])
            conn.commit()

        # Seed categories & sample products if empty
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO categories (name) VALUES (?)", [
                ("Electronics",), ("Groceries",), ("Fashion",)
            ])
            conn.commit()
            cur.executemany("INSERT INTO products (name, description, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?, ?)", [
                ("Wireless Earbuds", "High quality Bluetooth wireless earbuds with noise cancellation.", 45.00, 50, "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500", 1),
                ("Smart Watch", "Fitness tracker and smartwatch with heart rate monitor.", 85.50, 30, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500", 1),
                ("Organic Honey", "100% pure natural organic honey 500g jar.", 12.00, 100, "https://images.unsplash.com/photo-1587049352847-4a222e784d38?w=500", 2),
                ("Casual Cotton T-Shirt", "Comfortable 100% cotton breathable summer t-shirt.", 18.25, 75, "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500", 3)
            ])
            conn.commit()
        conn.close()

    # User Auth & Management
    def register_user(self, name, email, password, role="customer"):
        conn = self.get_connection()
        try:
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            conn.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                         (name, email, hashed_pw, role))
            conn.commit()
            conn.close()
            return True, "User registered successfully."
        except sqlite3.IntegrityError:
            conn.close()
            return False, "Email already registered."
        except Exception as e:
            conn.close()
            return False, str(e)

    def login_user(self, email, password):
        conn = self.get_connection()
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        user = conn.execute("SELECT id, name, email, role FROM users WHERE email = ? AND password = ?",
                            (email, hashed_pw)).fetchone()
        conn.close()
        return dict(user) if user else None

    def get_all_users(self):
        conn = self.get_connection()
        users = conn.execute("SELECT id, name, email, role FROM users").fetchall()
        conn.close()
        return [dict(u) for u in users]

    # Product Operations
    def get_products(self, category_id=None, search=None):
        conn = self.get_connection()
        query = "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE 1=1"
        params = []
        if category_id:
            query += " AND p.category_id = ?"
            params.append(category_id)
        if search:
            query += " AND (p.name LIKE ? OR p.description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        products = conn.execute(query, params).fetchall()
        categories = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        return {"products": [dict(p) for p in products], "categories": [dict(c) for c in categories]}

    def get_product_by_id(self, product_id):
        conn = self.get_connection()
        prod = conn.execute("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", (product_id,)).fetchone()
        conn.close()
        return dict(prod) if prod else None

    def add_product(self, name, description, price, stock, image_url, category_id):
        conn = self.get_connection()
        conn.execute("INSERT INTO products (name, description, price, stock, image_url, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                     (name, description, float(price), int(stock), image_url, int(category_id)))
        conn.commit()
        conn.close()
        return True, "Product added successfully."

    def update_inventory(self, product_id, stock):
        conn = self.get_connection()
        conn.execute("UPDATE products SET stock = ? WHERE id = ?", (int(stock), int(product_id)))
        conn.commit()
        conn.close()
        return True, "Inventory updated."

    # Cart Operations
    def add_to_cart(self, user_id, product_id, quantity=1):
        conn = self.get_connection()
        existing = conn.execute("SELECT id, quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
                                (user_id, product_id)).fetchone()
        if existing:
            new_qty = existing['quantity'] + quantity
            conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, existing['id']))
        else:
            conn.execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                         (user_id, product_id, quantity))
        conn.commit()
        conn.close()
        return True, "Added to cart."

    def get_cart(self, user_id):
        conn = self.get_connection()
        items = conn.execute("""
            SELECT ci.id, ci.quantity, p.id as product_id, p.name, p.price, p.image_url, p.stock
            FROM cart_items ci JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = ?
        """, (user_id,)).fetchall()
        conn.close()
        return [dict(item) for item in items]

    def remove_from_cart(self, cart_item_id):
        conn = self.get_connection()
        conn.execute("DELETE FROM cart_items WHERE id = ?", (cart_item_id,))
        conn.commit()
        conn.close()
        return True, "Item removed."

    # Order Lifecycle & Checkout
    def checkout(self, user_id, payment_method, bkash_trx_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cart = cursor.execute("""
                SELECT ci.product_id, ci.quantity, p.price, p.stock, p.name
                FROM cart_items ci JOIN products p ON ci.product_id = p.id
                WHERE ci.user_id = ?
            """, (user_id,)).fetchall()

            if not cart:
                conn.close()
                return False, "Cart is empty."

            total_amount = 0
            for item in cart:
                if item['stock'] < item['quantity']:
                    conn.close()
                    return False, f"Insufficient stock for {item['name']}."
                total_amount += item['price'] * item['quantity']

            payment_status = "Paid" if payment_method == "bKash" else "Pending"
            
            cursor.execute("""
                INSERT INTO orders (user_id, total_amount, payment_method, payment_status, order_status, bkash_trx_id)
                VALUES (?, ?, ?, ?, 'Processing', ?)
            """, (user_id, total_amount, payment_method, payment_status, bkash_trx_id))
            order_id = cursor.lastrowid

            for item in cart:
                subtotal = item['price'] * item['quantity']
                cursor.execute("""
                    INSERT INTO order_items (order_id, product_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                """, (order_id, item['product_id'], item['quantity'], item['price']))
                cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['quantity'], item['product_id']))

            cursor.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True, f"Order #{order_id} placed successfully!"
        except Exception as e:
            conn.close()
            return False, str(e)

    def get_orders(self, user_id=None, is_admin=False):
        conn = self.get_connection()
        if is_admin:
            orders = conn.execute("""
                SELECT o.*, u.name as customer_name, u.email as customer_email
                FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC
            """).fetchall()
        else:
            orders = conn.execute("""
                SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC
            """, (user_id,)).fetchall()
        
        result = []
        for o in orders:
            ord_dict = dict(o)
            items = conn.execute("""
                SELECT oi.*, p.name as product_name, p.image_url
                FROM order_items oi JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (o['id'],)).fetchall()
            ord_dict['items'] = [dict(i) for i in items]
            result.append(ord_dict)
        conn.close()
        return result

    def update_order_status(self, order_id, status):
        conn = self.get_connection()
        conn.execute("UPDATE orders SET order_status = ? WHERE id = ?", (status, order_id))
        conn.commit()
        conn.close()
        return True, "Order status updated."

    # Settings & Gateway API
    def get_settings(self):
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM settings").fetchall()
        conn.close()
        return {r['key']: r['value'] for r in rows}

    def update_setting(self, key, value):
        conn = self.get_connection()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        return True, "Setting updated."
