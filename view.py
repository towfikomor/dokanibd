import os

class ECommerceView:
    def __init__(self, template_dir="templates"):
        self.template_dir = template_dir

    def render_template(self, filename):
        path = os.path.join(self.template_dir, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return b"<h1>404 Template Not Found</h1>"
