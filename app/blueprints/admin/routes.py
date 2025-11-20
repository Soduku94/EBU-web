from flask import render_template, flash, redirect, url_for,request
from . import admin
from .forms import CategoryForm, ProductForm, PostForm
from app.models import Category, Product, Post, Order, ContactMessage
from app.extensions import db
from app.decorators import admin_required  # Import decorator bảo vệ
from flask_login import login_required, current_user
from sqlalchemy import func
import os
from werkzeug.utils import secure_filename
import uuid # Để tạo tên file ngẫu nhiên, tránh trùng lặp
from flask import current_app # Để truy cập đường dẫn static

import csv
import io
from flask import Response, make_response
from slugify import slugify



def save_picture(form_picture):
    """Hàm lưu file ảnh vào thư mục static/uploads và trả về tên file."""
    # 1. Lấy tên file gốc an toàn
    original_filename = secure_filename(form_picture.filename)

    # 2. Tạo tên file mới ngẫu nhiên để tránh trùng lặp (ví dụ: a8f9d0_tate.jpg)
    random_hex = uuid.uuid4().hex[:8]
    _, f_ext = os.path.splitext(original_filename)
    picture_fn = random_hex + f_ext

    # 3. Xác định thư mục chứa ảnh
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')

    # Ktra xem thư mục có tồn tại không, nếu không thì TẠO MỚI
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    # Tạo đường dẫn đầy đủ của file
    picture_path = os.path.join(upload_dir, picture_fn)

    # 4. Lưu file
    form_picture.save(picture_path)

    # 5. Trả về đường dẫn tương đối để lưu vào database
    return 'uploads/' + picture_fn

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
#lưu ảnh
        image_path = None
        if form.image.data:
            image_path = save_picture(form.image.data)

        # Lấy đối tượng Category từ form
        category_obj = form.category.data
        base_slug = slugify(form.name.data)
        unique_slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"
        # Tạo sản phẩm mới
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            image_url=image_path,
            category=category_obj,
            slug=unique_slug

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





@admin.route('/orders/export')
@login_required
@admin_required
def export_orders():
    """Xuất danh sách đơn hàng ra file CSV (Excel)."""

    # 1. Lấy tất cả đơn hàng
    orders = Order.query.order_by(Order.order_date.desc()).all()

    # 2. Tạo file CSV trong bộ nhớ (RAM) thay vì lưu ra ổ cứng
    # Dùng io.StringIO để xử lý văn bản
    output = io.StringIO()
    writer = csv.writer(output)

    # 3. Viết dòng Tiêu đề (Header)
    # Lưu ý: Thứ tự cột phải khớp với dữ liệu bên dưới
    writer.writerow(
        ['Mã Đơn', 'Ngày đặt', 'Khách hàng', 'Email', 'SĐT', 'Địa chỉ', 'Tổng tiền', 'PT Thanh toán', 'Trạng thái'])

    # 4. Viết dữ liệu từng đơn hàng
    for order in orders:
        writer.writerow([
            order.id,
            order.order_date.strftime('%d/%m/%Y %H:%M'),  # Định dạng ngày
            order.customer_name,
            order.customer_email,
            order.customer_phone,
            order.shipping_address,
            f"{order.total_price:.0f}",  # Số tiền (bỏ số thập phân)
            order.payment_method,
            order.status
        ])

    # 5. Chuẩn bị dữ liệu để trả về
    # Quan trọng: Cần encode 'utf-8-sig' để Excel hiển thị đúng tiếng Việt
    csv_data = output.getvalue().encode('utf-8-sig')

    # 6. Tạo Response trả về file
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=danh_sach_don_hang.csv"}
    )




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


@admin.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    form = ProductForm()

    if form.validate_on_submit():
        # Cập nhật thông tin từ form
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.category = form.category.data

        # Cập nhật Slug (nếu tên thay đổi)
        from slugify import slugify
        import uuid
        # Tạo slug mới để đảm bảo đồng bộ với tên mới
        base_slug = slugify(form.name.data)
        product.slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"

        # Xử lý ảnh (Chỉ cập nhật nếu người dùng upload ảnh mới)
        if form.image.data:
            # (Tùy chọn: Xóa ảnh cũ để tiết kiệm dung lượng server)
            # ...
            image_path = save_picture(form.image.data)
            product.image_url = image_path

        db.session.commit()
        flash('Đã cập nhật sản phẩm thành công!', 'success')
        return redirect(url_for('admin.manage_products'))

    # Khi vào trang (GET), điền sẵn dữ liệu cũ vào form
    elif request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.stock.data = product.stock
        form.category.data = product.category
        # Không cần điền form.image.data vì đó là file upload

    return render_template('admin/edit_product.html',
                           title='Sửa Sản phẩm',
                           form=form,
                           product=product)


# === 2. ROUTE XÓA SẢN PHẨM (DELETE) ===
@admin.route('/product/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)

    # (Tùy chọn: Kiểm tra xem sản phẩm có đang nằm trong đơn hàng nào không
    #  để tránh lỗi khóa ngoại ForeignKey.
    #  Tạm thời chúng ta xóa thẳng, nếu có lỗi database sẽ báo)

    try:
        db.session.delete(product)
        db.session.commit()
        flash('Đã xóa sản phẩm thành công.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Không thể xóa sản phẩm này (có thể do đang có đơn hàng liên quan).', 'danger')
        print(e)

    return redirect(url_for('admin.manage_products'))


