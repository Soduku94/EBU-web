# Standard library
import os
import secrets
import uuid
import csv
import io
from datetime import datetime, timedelta

# Third-party
from slugify import slugify
from sqlalchemy import func
from werkzeug.utils import secure_filename

# Flask
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    current_app,
    Response,
    make_response
)
from flask_login import login_required, current_user

# Project imports
from . import admin
from .forms import CategoryForm, ProductForm, PostForm
from app.models import Category, Product, Post, Order, ContactMessage
from app.extensions import db
from app.decorators import admin_required
from app.models import Coupon
from .forms import CouponForm

from app.models import ProductImage  # Nhớ import


def save_additional_images(product, files):
    upload_folder = os.path.join(current_app.root_path, 'static', 'images', 'products')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            unique_filename = f"extra_{int(datetime.utcnow().timestamp())}_{filename}"

            # Lưu file vật lý
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)

            # Lưu DB: Phải khớp với save_picture
            db_path = f"images/products/{unique_filename}"

            new_image = ProductImage(image_url=db_path, product=product)
            db.session.add(new_image)

    db.session.commit()


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext

    # 1. Đường dẫn vật lý (để lưu file): app/static/images/products
    upload_folder = os.path.join(current_app.root_path, 'static', 'images', 'products')

    # Tạo thư mục nếu chưa có
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    picture_path = os.path.join(upload_folder, picture_fn)

    # Lưu file
    form_picture.save(picture_path)

    # 2. Đường dẫn Database (QUAN TRỌNG): Phải trả về đường dẫn tương đối từ 'static'
    # Đừng trả về 'uploads/' nữa, hãy đổi thành 'images/products/'
    return f"images/products/{picture_fn}"

@admin.route('/')
@login_required
@admin_required
def index():
    # MỚI: Phải "Đã thanh toán" (is_paid = True) mới tính là Doanh thu
    total_revenue = db.session.query(func.sum(Order.total_price)) \
                        .filter(Order.is_paid == True).scalar() or 0


    order_count = Order.query.filter(Order.status != 'Cancelled').count()
    product_count = Product.query.count()

    from app.models import User
    user_count = User.query.count()

    # === PHẦN 2: TÍNH TOÁN BIỂU ĐỒ (7 NGÀY GẦN NHẤT) ===

    # A. Tạo khung dữ liệu cho 7 ngày qua (mặc định doanh thu là 0)
    # Kết quả mong muốn: { '2023-11-15': 0, '2023-11-16': 0, ... }
    revenue_map = {}
    today = datetime.now().date()

    for i in range(6, -1, -1):  # Lùi lại 6 ngày trước đến hôm nay
        date_key = today - timedelta(days=i)
        revenue_map[date_key] = 0

    # B. Lấy các đơn hàng thành công trong 7 ngày qua
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_orders = Order.query.filter(
        Order.order_date >= seven_days_ago,
        Order.status != 'Cancelled',  # Chỉ tính đơn chưa hủy
        Order.is_paid == True
    ).all()

    # C. Cộng tiền vào đúng ngày trong map
    for order in recent_orders:
        # Chuyển đổi timestamp của đơn hàng sang date (ngày/tháng/năm)
        order_date = order.order_date.date()

        # Nếu ngày này nằm trong 7 ngày chúng ta đang xét
        if order_date in revenue_map:
            revenue_map[order_date] += order.total_price

    # D. Tách ra 2 danh sách để gửi cho Chart.js
    # labels: ['14/11', '15/11', ...]
    # values: [0, 500000, 120000, ...]
    chart_labels = [date.strftime('%d/%m') for date in revenue_map.keys()]
    chart_values = list(revenue_map.values())

    return render_template('admin/dashboard.html',
                           title='Admin Dashboard',
                           total_revenue=total_revenue,
                           order_count=order_count,
                           product_count=product_count,
                           user_count=user_count,
                           # Gửi dữ liệu biểu đồ
                           chart_labels=chart_labels,
                           chart_values=chart_values)

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
        # 1. Cập nhật thông tin cơ bản
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.category = form.category.data
        # product.is_active = form.is_active.data (Nếu form có field này)

        # 2. Cập nhật Slug (Chỉ khi tên thay đổi để tối ưu SEO)
        if product.name != form.name.data: # Kiểm tra xem tên có đổi không
            from slugify import slugify
            import uuid
            base_slug = slugify(form.name.data)
            product.slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"

        # 3. Xử lý Ảnh Chính (Chỉ cập nhật nếu có upload mới)
        if form.image.data:
            image_path = save_picture(form.image.data) # Hàm này bạn đã có
            product.image_url = image_path

        # 4. Xử lý Ảnh Phụ (ĐÃ SỬA: Đưa ra ngoài khối if của ảnh chính)
        new_files = form.additional_images.data
        # Kiểm tra kỹ: new_files phải tồn tại và file đầu tiên phải có tên (tránh upload rỗng)
        if new_files and new_files[0].filename:
            save_additional_images(product, new_files) # Hàm chúng ta vừa viết ở bước trước

        db.session.commit()
        flash('Đã cập nhật sản phẩm thành công!', 'success')
        return redirect(url_for('admin.manage_products'))

    # Khi vào trang (GET), điền sẵn dữ liệu cũ
    elif request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.stock.data = product.stock
        form.category.data = product.category
        # Ảnh không cần điền data

    return render_template('admin/edit_product.html',
                           title='Sửa Sản phẩm',
                           form=form,
                           product=product)


@admin.route('/product/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    form = ProductForm()

    if form.validate_on_submit():
        # 1. Tạo Slug
        from slugify import slugify
        import uuid
        base_slug = slugify(form.name.data)
        slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"

        # 2. Xử lý Ảnh Chính
        image_url = None
        if form.image.data:
            image_url = save_picture(form.image.data)

        # 3. Tạo đối tượng Product
        new_product = Product(
            name=form.name.data,
            slug=slug,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            category=form.category.data,
            image_url=image_url,
            is_active=True  # Mặc định là đang bán
        )

        # Lưu Product trước để có ID (cần ID để liên kết ảnh phụ)
        db.session.add(new_product)
        db.session.commit()

        # 4. Xử lý Ảnh Phụ (Sau khi đã có new_product)
        files = form.additional_images.data
        if files and files[0].filename:
            save_additional_images(new_product, files)

        flash(f'Đã thêm sản phẩm "{new_product.name}" thành công!', 'success')
        return redirect(url_for('admin.manage_products'))

    return render_template('admin/add_product.html', title='Thêm Sản phẩm', form=form)





# Đổi tên hàm cho đúng ý nghĩa (hoặc giữ nguyên tên route cũ cũng được, nhưng sửa logic)
@admin.route('/product/toggle/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_product(id):
    """Hàm bật/tắt trạng thái sản phẩm (Ẩn/Hiện)."""
    product = Product.query.get_or_404(id)

    # Logic đảo ngược trạng thái (Toggle)
    # Nếu đang True -> thành False
    # Nếu đang False -> thành True
    product.is_active = not product.is_active

    db.session.commit()

    # Thông báo tùy theo trạng thái mới
    status_msg = "được hiển thị trở lại" if product.is_active else "bị ẩn đi"
    flash(f'Sản phẩm "{product.name}" đã {status_msg}.', 'success')

    return redirect(url_for('admin.manage_products'))

# === QUẢN LÝ COUPON ===
@admin.route('/coupons', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_coupons():
    form = CouponForm()
    if form.validate_on_submit():
        coupon = Coupon(
            code=form.code.data.upper(), # Luôn lưu chữ in hoa
            discount_type=form.discount_type.data,
            discount_value=form.discount_value.data,
            min_order_value=form.min_order_value.data,
            expiration_date=form.expiration_date.data,
            active=form.active.data
        )
        db.session.add(coupon)
        db.session.commit()
        flash('Đã tạo mã giảm giá thành công!', 'success')
        return redirect(url_for('admin.manage_coupons'))

    coupons = Coupon.query.order_by(Coupon.id.desc()).all()
    return render_template('admin/coupons.html', title='Quản lý Mã giảm giá', form=form, coupons=coupons)

@admin.route('/coupon/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_coupon(id):
    coupon = Coupon.query.get_or_404(id)
    db.session.delete(coupon)
    db.session.commit()
    flash('Đã xóa mã giảm giá.', 'success')
    return redirect(url_for('admin.manage_coupons'))

@admin.route('/order/<int:order_id>/invoice')
@login_required
@admin_required
def print_invoice(order_id):
    """Trang in hóa đơn/phiếu giao hàng (Giao diện tối giản để in)."""
    order = Order.query.get_or_404(order_id)
    # Tính lại danh sách item để hiển thị
    return render_template('admin/invoice.html', order=order)


@admin.route('/order/<int:order_id>/confirm-payment', methods=['POST'])
@login_required
@admin_required
def confirm_payment(order_id):
    """Admin xác nhận đã nhận được tiền (cho đơn COD)."""
    order = Order.query.get_or_404(order_id)

    order.is_paid = True
    # Thường khi nhận tiền xong tức là đơn cũng hoàn thành
    if order.status != 'Delivered':
        order.status = 'Delivered'  # Hoặc trạng thái nào bạn muốn

    db.session.commit()
    flash(f'Đã xác nhận nhận tiền cho đơn #{order.id}. Doanh thu đã được cập nhật.', 'success')
    return redirect(url_for('admin.order_detail', order_id=order.id))