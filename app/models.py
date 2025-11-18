from datetime import datetime
from .extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# --- Models liên quan đến User và Roles ---

class Role(db.Model):
    """Bảng Role (Vai trò): Admin, Customer."""
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    # lazy='dynamic' giúp truy vấn hiệu quả hơn
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    """Bảng User: Lưu trữ thông tin người dùng (Khách và Admin)."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(256))  # Không lưu password gốc

    # Thông tin cá nhân (có thể thêm sau)
    # full_name = db.Column(db.String(128))
    # phone = db.Column(db.String(20))
    # address = db.Column(db.String(256))

    # Khóa ngoại liên kết với Role
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    reviews = db.relationship('Review', backref='author', lazy='dynamic')
    posts = db.relationship('Post', backref='author', lazy='dynamic')
# db mới
    # === THÊM CÁC TRƯỜNG MỚI CHO USER (để auto-fill khi checkout) ===
    full_name = db.Column(db.String(128))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(256))








    # Hàm để set password (hash)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Hàm để kiểm tra password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


# Hàm callback này được Flask-Login sử dụng để tải user từ session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Models liên quan đến Sản phẩm (Product) ---

class Category(db.Model):
    """Bảng Category (Danh mục sản phẩm): Tạ, Thảm, Máy chạy..."""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True)
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    """Bảng Product (Sản phẩm)."""
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float)  # Dùng Float cho đơn giản, Numeric nếu cần độ chính xác tuyệt đối
    stock = db.Column(db.Integer)  # Số lượng hàng tồn kho
    image_url = db.Column(db.String(512))  # Đường dẫn đến ảnh sản phẩm

    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    reviews = db.relationship('Review', backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name}>'


# --- Models liên quan đến Đơn hàng (Order) ---

class Order(db.Model):
    """Bảng Order (Đơn hàng)."""
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(64), default='Pending')  # (Pending, Confirmed, Shipped, Cancelled)
    total_price = db.Column(db.Float)

    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Chứa tất cả các 'món hàng' trong đơn hàng này
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')

    # === THAY ĐỔI VÀ THÊM MỚI ===
    # 1. Cho phép customer_id bị rỗng (nullable=True) cho khách vãng lai
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # phương thức thanh toán (mặc định sẽ là cash on delivery )
    payment_method = db.Column(db.String(64), default='COD')

    # 2. Thêm các trường để lưu thông tin của khách (kể cả khách vãng lai)
    customer_name = db.Column(db.String(128))
    customer_email = db.Column(db.String(128), index=True)
    customer_phone = db.Column(db.String(20))
    shipping_address = db.Column(db.Text)




    def __repr__(self):
        return f'<Order {self.id}>'


class OrderItem(db.Model):
    """
    Bảng Chi tiết đơn hàng (các món hàng trong 1 đơn).
    Đây là bảng trung gian giữa Order và Product.
    """
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer)
    price_at_purchase = db.Column(db.Float)  # Lưu lại giá tại thời điểm mua

    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))

    # Thêm 1 relationship nhỏ để dễ truy cập Product từ OrderItem
    product = db.relationship('Product')

    def __repr__(self):
        return f'<OrderItem Order {self.order_id} Product {self.product_id}>'


# --- Models liên quan đến Blog và Đánh giá ---

class Post(db.Model):
    """Bảng Post (Bài đăng Blog)."""
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<Post {self.title}>'


class Review(db.Model):
    """Bảng Review (Đánh giá sản phẩm)."""
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer)  # (Từ 1 đến 5 sao)
    comment = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))

    def __repr__(self):
        return f'<Review by User {self.author_id} for Product {self.product_id}>'




class ContactMessage(db.Model):
    """Bảng lưu các tin nhắn từ Form Liên hệ."""
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    email = db.Column(db.String(128), index=True)
    subject = db.Column(db.String(256))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False) # Để Admin đánh dấu "đã đọc"

    def __repr__(self):
        return f'<ContactMessage {self.subject}>'