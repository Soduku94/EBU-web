from flask import render_template, flash, redirect, url_for,request
from . import admin
from .forms import CategoryForm, ProductForm, PostForm
from app.models import Category, Product, Post, Order, ContactMessage
from app.extensions import db
from app.decorators import admin_required  # Import decorator bảo vệ
from flask_login import login_required, current_user
from sqlalchemy import func

@admin.route('/')
@login_required
@admin_required
def index():
    # 1. Tổng Doanh thu (Chỉ tính đơn hàng KHÔNG bị hủy)
    total_revenue = db.session.query(func.sum(Order.total_price))\
        .filter(Order.status != 'Cancelled').scalar() or 0

    # 2. Tổng số đơn hàng (Không tính đơn hủy)
    order_count = Order.query.filter(Order.status != 'Cancelled').count()

    # 3. Tổng số sản phẩm
    product_count = Product.query.count()

    # 4. Số lượng khách hàng (User có role Customer)
    # (Cần import Role nếu chưa có)
    # customer_count = User.query.join(Role).filter(Role.name == 'Customer').count()
    # Tạm thời lấy tổng user cho đơn giản
    from app.models import User
    user_count = User.query.count()

    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           total_revenue=total_revenue,
                           order_count=order_count,
                           product_count=product_count,
                           user_count=user_count)

# Trang quản lý danh mục
@admin.route('/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories():
    form = CategoryForm()
    if form.validate_on_submit():
        # Tạo danh mục mới
        category = Category(name=form.name.data)
        db.session.add(category)
        db.session.commit()
        flash('Đã thêm danh mục mới thành công!', 'success')
        return redirect(url_for('admin.manage_categories'))

    # Lấy tất cả danh mục
    categories = Category.query.all()
    return render_template('admin/categories.html',
                           title='Quản lý Danh mục',
                           form=form,
                           categories=categories)


@admin.route('/products', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_products():
    form = ProductForm()

    if form.validate_on_submit():
        # Lấy đối tượng Category từ form
        category_obj = form.category.data

        # Tạo sản phẩm mới
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            image_url=form.image_url.data,
            category=category_obj  # Gán cả đối tượng Category
        )
        db.session.add(product)
        db.session.commit()
        flash('Đã thêm sản phẩm mới thành công!', 'success')
        return redirect(url_for('admin.manage_products'))

    # Lấy tất cả sản phẩm hiện có
    # .options(db.joinedload('category')) giúp tải category ngay lập tức,
    # tránh lỗi N+1 query khi hiển thị ở template
    products = Product.query.options(db.joinedload(Product.category)).all()

    return render_template('admin/products.html',
                           title='Quản lý Sản phẩm',
                           form=form,
                           products=products)


# === THÊM ROUTE MỚI VÀO ĐÂY ===

@admin.route('/posts')
@login_required
@admin_required
def manage_posts():
    """Hiển thị danh sách bài viết (đã Phân trang)."""
    page = request.args.get('page', 1, type=int)

    # Hiển thị 10 bài viết mỗi trang
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    posts = pagination.items

    return render_template('admin/posts.html',
                           title='Quản lý Blog',
                           posts=posts,
                           pagination=pagination) # <-- Gửi pagination

@admin.route('/posts/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_post():
    """Form thêm bài viết mới."""
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data,
            body=form.body.data,
            author=current_user  # Gán tác giả là admin đang đăng nhập
        )
        db.session.add(post)
        db.session.commit()
        flash('Đã đăng bài viết mới thành công!', 'success')
        return redirect(url_for('admin.manage_posts'))

    return render_template('admin/add_post.html', title='Viết bài mới', form=form)


# === THÊM 2 ROUTE MỚI VÀO CUỐI FILE ===

@admin.route('/orders')
@login_required
@admin_required
def manage_orders():
    """Trang xem danh sách tất cả đơn hàng (đã Phân trang)."""
    # 1. Lấy số trang từ URL (ví dụ: /orders?page=2), mặc định là trang 1
    page = request.args.get('page', 1, type=int)

    # 2. Thay thế .all() bằng .paginate()
    # Chúng ta sẽ hiển thị 10 đơn hàng mỗi trang
    pagination = Order.query.order_by(Order.order_date.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    # 'pagination.items' chứa danh sách 10 đơn hàng của trang hiện tại
    orders = pagination.items

    return render_template('admin/orders.html',
                           title='Quản lý Đơn hàng',
                           orders=orders,
                           pagination=pagination) # <-- Gửi cả đối tượng pagination

@admin.route('/order/<int:order_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def order_detail(order_id):
    """Trang xem chi tiết và cập nhật 1 đơn hàng."""
    order = Order.query.get_or_404(order_id)

    # Lấy các trạng thái đơn hàng có thể có
    # (Sau này có thể đưa vào 1 model riêng, tạm thời để list)
    statuses = ['Pending', 'Confirmed', 'Shipped', 'Delivered', 'Cancelled']

    if request.method == 'POST':
        # Admin nhấn nút "Cập nhật trạng thái"
        new_status = request.form.get('status')
        if new_status in statuses:
            order.status = new_status
            db.session.commit()
            flash(f'Đã cập nhật trạng thái đơn hàng #{order.id} thành "{new_status}"', 'success')
        else:
            flash('Trạng thái không hợp lệ.', 'danger')
        return redirect(url_for('admin.order_detail', order_id=order.id))

    return render_template('admin/order_detail.html',
                           title=f'Chi tiết Đơn hàng #{order.id}',
                           order=order,
                           statuses=statuses)


@admin.route('/messages')
@login_required
@admin_required
def manage_messages():
    """Trang xem danh sách tất cả tin nhắn liên hệ (đã Phân trang)."""
    page = request.args.get('page', 1, type=int)

    # Hiển thị 10 tin nhắn mỗi trang
    pagination = ContactMessage.query.order_by(ContactMessage.timestamp.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    messages = pagination.items

    return render_template('admin/messages.html',
                           title='Hộp thư Liên hệ',
                           messages=messages,
                           pagination=pagination) # <-- Gửi pagination