# controller.py
import os
import http.server
import socketserver
import json
import urllib.request
import datetime
import urllib.error
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

        # Pages
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

        # API Endpoints
        elif path == "/api/products":
            cat_id = int(query.get('category_id', [0])[0]) or None
            search = query.get('search', [None])[0]
            data = model.get_products(cat_id, search)
            self.send_json(data)

        elif path == "/api/product":
            prod_id = int(query.get('id', [0])[0])
            prod = model.get_product_by_id(prod_id)
            self.send_json(prod or {})

        elif path == "/api/cart":
            user_id = int(query.get('user_id', [0])[0])
            items = model.get_cart(user_id)
            self.send_json(items)

        elif path == "/api/orders":
            user_id = int(query.get('user_id', [0])[0])
            is_admin = query.get('is_admin', ['false'])[0].lower() == 'true'
            orders = model.get_orders(user_id, is_admin)
            self.send_json(orders)

        elif path == "/api/settings":
            settings = model.get_settings()
            # Mask sensitive API secrets when sent to public/frontend settings API
            safe_settings = {
                "bkash_enabled": settings.get("bkash_enabled"),
                "bkash_sandbox": settings.get("bkash_sandbox")
            }
            self.send_json(safe_settings)

        elif path == "/api/admin/settings":
            self.send_json(model.get_settings())

        elif path == "/api/admin/users":
            users = model.get_all_users()
            self.send_json(users)

        # bKash Payment Callback Handlers (Redirected from bKash payment gateway page)
        elif path == "/api/bkash/callback":
            status = query.get('status', ['fail'])[0]
            payment_id = query.get('paymentID', [None])[0]
            user_id = query.get('user_id', [None])[0]

            if status == 'success' and payment_id and user_id:
                # Call bKash Execute Payment API to finalize transaction
                success, trx_id_or_msg = self.execute_bkash_payment(payment_id)
                if success:
                    model.create_order_record(int(user_id), "bKash", trx_id_or_msg)
                    self.redirect("/orders.html")
                    return
            
            self.redirect("/cart.html?error=bkash_payment_failed")

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
            user_id = body.get('user_id')
            method = body.get('payment_method')

            if method == "bKash":
                # Initialize bKash Tokenized Checkout Create Payment API
                redirect_url, err = self.initiate_bkash_checkout(user_id)
                if redirect_url:
                    self.send_json({"success": True, "bkashURL": redirect_url})
                else:
                    self.send_json({"success": False, "message": err or "Failed to initiate bKash payment."}, status=400)
            else:
                # Regular Cash on Delivery (COD) Checkout
                order_id, msg = model.create_order_record(user_id, method)
                self.send_json({"success": bool(order_id), "message": msg}, status=200 if order_id else 400)

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

    # --- bKash API Integration Service Methods ---
    def get_bkash_base_url(self):
        settings = model.get_settings()
        is_sandbox = settings.get("bkash_sandbox", "true") == "true"
        return "https://tokenized.sandbox.bka.sh/v1.2.0-beta" if is_sandbox else "https://tokenized.pay.bka.sh/v1.2.0-beta"

    def get_bkash_grant_token(self):
        settings = model.get_settings()
        base_url = self.get_bkash_base_url()
        url = f"{base_url}/tokenized/checkout/token/grant"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "username": settings.get("bkash_username", ""),
            "password": settings.get("bkash_password", "")
        }
        data = json.dumps({
            "app_key": settings.get("bkash_app_key", ""),
            "app_secret": settings.get("bkash_app_secret", "")
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data.get("id_token")
        except Exception as e:
            print("bKash Grant Token Error:", e)
            return None

    def initiate_bkash_checkout(self, user_id):
        cart_items = model.get_cart(user_id)
        if not cart_items:
            return None, "Cart is empty."

        total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
        id_token = self.get_bkash_grant_token()
        if not id_token:
            return None, "Unable to authorize with bKash API. Verify your credentials in Admin Panel."

        base_url = self.get_bkash_base_url()
        url = f"{base_url}/tokenized/checkout/create"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": id_token,
            "X-APP-Key": model.get_settings().get("bkash_app_key", "")
        }

        callback_domain = "http://localhost:8000" # Update to your production domain if live
        payload = json.dumps({
            "mode": "0011",
            "payerReference": f"User-{user_id}",
            "callbackURL": f"{callback_domain}/api/bkash/callback?user_id={user_id}",
            "merchantAssociationInfo": "MI01ABC",
            "amount": str(total_amount),
            "currency": "BDT",
            "intent": "sale",
            "merchantInvoiceNumber": f"INV-{user_id}-{int(datetime.datetime.now().timestamp())}"
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("statusCode") == "0000":
                    return res_data.get("bkashURL"), None
                return None, res_data.get("statusMessage", "bKash payment initialization failed.")
        except Exception as e:
            print("bKash Create Payment Error:", e)
            return None, str(e)

    def execute_bkash_payment(self, payment_id):
        id_token = self.get_bkash_grant_token()
        if not id_token:
            return False, "Token authorization failed."

        base_url = self.get_bkash_base_url()
        url = f"{base_url}/tokenized/checkout/execute"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": id_token,
            "X-APP-Key": model.get_settings().get("bkash_app_key", "")
        }
        payload = json.dumps({"paymentID": payment_id}).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("statusCode") == "0000":
                    trx_id = res_data.get("trxID")
                    return True, trx_id
                return False, res_data.get("statusMessage", "Execution failed.")
        except Exception as e:
            print("bKash Execute Payment Error:", e)
            return False, str(e)

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

    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

if __name__ == "__main__":
    server_address = ("", PORT)
    httpd = socketserver.TCPServer(server_address, ECommerceHandler)
    print(f"🚀 Dokanibd Server running at http://localhost:{PORT}")
    httpd.serve_forever()