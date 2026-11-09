# controller.py
import os
import http.server
import socketserver
import json
from urllib.parse import urlparse, parse_qs
from model import ECommerceModel
from view import ECommerceView

PORT = int(os.environ.get("PORT", 8000))
model = ECommerceModel()
view = ECommerceView()

class ECommerceHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_file("index.html")
        elif path == "/login.html":
            self.serve_file("login.html")
        elif path == "/signup.html":
            self.serve_file("signup.html")
        elif path == "/cart.html":
            self.serve_file("cart.html")
        elif path == "/orders.html":
            self.serve_file("orders.html")
        elif path == "/product.html":
            self.serve_file("product.html")
        elif path == "/admin.html":
            self.serve_file("admin.html")
        elif path == "/api/products":
            cat_id = int(query.get('category_id', [0])[0]) or None
            search = query.get('search', [None])[0]
            self.send_json(model.get_products(cat_id, search))
        elif path == "/api/product":
            prod_id = int(query.get('id', [0])[0])
            self.send_json(model.get_product_by_id(prod_id) or {})
        elif path == "/api/cart":
            user_id = int(query.get('user_id', [0])[0])
            self.send_json(model.get_cart(user_id))
        elif path == "/api/orders":
            user_id = int(query.get('user_id', [0])[0])
            is_admin = query.get('is_admin', ['false'])[0].lower() == 'true'
            self.send_json(model.get_orders(user_id, is_admin))
        elif path == "/api/settings":
            self.send_json(model.get_settings())
        elif path == "/api/admin/users":
            self.send_json(model.get_all_users())
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}

        if path == "/api/signup":
            success, msg = model.register_user(body.get('name'), body.get('email'), body.get('password'), body.get('role', 'customer'))
            self.send_json({"success": success, "message": msg}, status=200 if success else 400)
        elif path == "/api/login":
            user = model.login_user(body.get('email'), body.get('password'))
            if user:
                self.send_json({"success": True, "user": user})
            else:
                self.send_json({"success": False, "message": "Invalid email or password."}, status=400)
        elif path == "/api/cart/add":
            success, msg = model.add_to_cart(body.get('user_id'), body.get('product_id'), body.get('quantity', 1))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/cart/remove":
            success, msg = model.remove_from_cart(body.get('cart_item_id'))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/checkout":
            success, msg = model.checkout(body.get('user_id'), body.get('payment_method'), body.get('bkash_trx_id'))
            self.send_json({"success": success, "message": msg}, status=200 if success else 400)
        elif path == "/api/admin/add_product":
            success, msg = model.add_product(body.get('name'), body.get('description'), body.get('price'), body.get('stock'), body.get('image_url'), body.get('category_id'))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/admin/inventory":
            success, msg = model.update_inventory(body.get('product_id'), body.get('stock'))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/admin/order_status":
            success, msg = model.update_order_status(body.get('order_id'), body.get('status'))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/admin/settings":
            success, msg = model.update_setting(body.get('key'), body.get('value'))
            self.send_json({"success": success, "message": msg})
        elif path == "/api/admin/create_user":
            success, msg = model.register_user(body.get('name'), body.get('email'), body.get('password'), body.get('role', 'customer'))
            self.send_json({"success": success, "message": msg}, status=200 if success else 400)
        else:
            self.send_error(404, "Endpoint Not Found")

    def serve_file(self, filename):
        content = view.render_template(filename)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def send_json(self, data, status=200):
        resp = json.dumps(data).encode('utf-8')
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(resp))
            self.end_headers()
            self.wfile.write(resp)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

if __name__ == "__main__":
    server_address = ("", PORT)
    httpd = socketserver.TCPServer(server_address, ECommerceHandler)
    print(f"🚀 Dokanibd Server running at http://localhost:{PORT}")
    httpd.serve_forever()