# Standard library
from datetime import datetime



# Third-party
import google.generativeai as genai

import os
import secrets
from flask import current_app

# Flask
from flask import (
    render_template,
    session,
    redirect,
    url_for,
    flash,
    request,
    current_app,

)
from flask_login import current_user, login_required

# Project - Blueprint
from . import main
from ..admin import admin
from ...decorators import admin_required

# Project - Forms
from .forms import (
    CheckoutForm,
    ReviewForm,
    TrackOrderForm,
    ContactForm,
    UpdateAccountForm,
    ChangePasswordForm, NeedsAssessmentForm,
)

# Project - Models
from app.models import (
    Product,
    Category,
    Order,
    OrderItem,
    Review,
    Post,
    ContactMessage
)

# Project - Services & Extensions
from app.extensions import db
from app.email import send_order_confirmation_email
from app.vnpay_service import (
    get_vnpay_payment_url,
    validate_vnpay_response
)
from app.models import Coupon
from datetime import datetime

from .forms import ParqForm
from app.models import HealthScreening

from flask import jsonify

from sqlalchemy.sql import func
@main.route('/')
@main.route('/index')
def index():
    # 1. Các query cũ giữ nguyên
    global func
    featured_products = Product.query.filter(Product.is_active == True).order_by(Product.id.desc()).limit(8).all()
    categories = Category.query.all()
    latest_posts = Post.query.order_by(Post.timestamp.desc()).limit(2).all()

    # Review 5 sao (giữ nguyên code của bạn)
    latest_reviews = Review.query.options(db.joinedload(Review.author), db.joinedload(Review.product)).join(
        Product).filter(Review.rating == 5, Product.is_active == True).order_by(Review.timestamp.desc()).limit(3).all()

    # === 2. QUERY HOT DEAL (MỚI) ===
    # Logic: Lấy Active -> Offset 15 (Bỏ 15 cái đầu) -> Limit 8 (Lấy 8 cái tiếp theo)
    hot_deal_products = Product.query.filter(Product.is_active == True) \
        .offset(15) \
        .limit(8).all()

    # Nếu database ít hơn 15 sản phẩm, list này sẽ rỗng.
    # Fallback: Nếu rỗng thì lấy random 8 cái bất kỳ để không bị trống trang web
    if not hot_deal_products:
        from sqlalchemy.sql.expression import func
        hot_deal_products = Product.query.filter(Product.is_active == True).order_by(func.random()).limit(8).all()

    best_sellers = Product.query.filter(Product.is_active == True).order_by(func.random()).limit(4).all()

    return render_template('index.html',
                           products=featured_products,
                           hot_deal_products=hot_deal_products,
                           categories=categories,
                           best_sellers=best_sellers,
                           latest_posts=latest_posts,
                           latest_reviews=latest_reviews)


@main.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    cart = session.get('cart', {})
    product = Product.query.get_or_404(product_id)
    product_id_str = str(product.id)

    # Lấy số lượng (Hỗ trợ cả Form thường và JSON nếu cần)
    try:
        quantity_to_add = int(request.form.get('quantity', '1'))
    except ValueError:
        quantity_to_add = 1
    if quantity_to_add <= 0:
        quantity_to_add = 1

    # Kiểm tra tồn kho
    current_quantity_in_cart = cart.get(product_id_str, 0)
    if current_quantity_in_cart + quantity_to_add > product.stock:
        msg = f'Xin lỗi, chỉ còn {product.stock} sản phẩm "{product.name}" trong kho.'

        # === LOGIC MỚI: KIỂM TRA AJAX ===
        # Nếu có header đặc biệt này, trả về JSON lỗi
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': msg})

        # Nếu không, chạy logic cũ (flash + redirect)
        flash(msg, 'warning')
        return redirect(request.referrer or url_for('main.index'))

    # Thêm vào giỏ
    if product_id_str in cart:
        cart[product_id_str] += quantity_to_add
    else:
        cart[product_id_str] = quantity_to_add

    session['cart'] = cart

    # Tính tổng số lượng mới để cập nhật badge
    new_cart_count = sum(cart.values())

    msg = f'Đã thêm {quantity_to_add} "{product.name}" vào giỏ hàng!'

    # === LOGIC MỚI: TRẢ VỀ JSON THÀNH CÔNG ===
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'message': msg,
            'cart_count': new_cart_count
        })

    # Logic cũ
    flash(msg, 'success')
    return redirect(request.referrer or url_for('main.index'))


# === 3. XEM GIỎ HÀNG ===
@main.route('/cart')
def view_cart():
    # Nếu người dùng quay lại giỏ hàng,
    # chúng ta hủy luồng "Mua Ngay" (nếu có)
    if 'is_buy_now' in session:
        session.pop('is_buy_now', None)
    if 'buy_now_cart' in session:
        session.pop('buy_now_cart', None)

    cart = session.get('cart', {})
    if not cart:
        # Nếu giỏ hàng rỗng
        return render_template('cart_empty.html')

    # Lấy ID sản phẩm từ keys của cart
    product_ids = [int(pid) for pid in cart.keys()]
    products_in_cart = Product.query.filter(Product.id.in_(product_ids)).all()

    cart_items = []
    total_price = 0
    for product in products_in_cart:
        product_id_str = str(product.id)
        quantity = cart[product_id_str]
        subtotal = product.price * quantity
        total_price += subtotal

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

    return render_template('cart.html',
                           items=cart_items,
                           total_price=total_price)


@main.route('/checkout', methods=['GET', 'POST'])
def checkout():
    # ==================================================================
    # PHẦN 1: LẤY GIỎ HÀNG & CHUẨN BỊ DỮ LIỆU HIỂN THỊ (GET)
    # ==================================================================

    # 1. Kiểm tra luồng "Mua Ngay" hay "Giỏ Hàng"
    is_buy_now = session.get('is_buy_now', False)
    if is_buy_now:
        cart = session.get('buy_now_cart', {})
    else:
        cart = session.get('cart', {})

    if not cart:
        flash('Giỏ hàng của bạn đang rỗng.', 'info')
        return redirect(url_for('main.index'))

    # 2. Tính toán dữ liệu để hiển thị ra giao diện (HTML)
    product_ids = [int(pid) for pid in cart.keys()]
    products_in_cart = Product.query.filter(Product.id.in_(product_ids)).all()

    items_for_display = []
    total_price = 0

    for product in products_in_cart:
        product_id_str = str(product.id)
        quantity = cart[product_id_str]

        # Cảnh báo tồn kho (chỉ hiển thị khi xem trang, không chặn)
        if quantity > product.stock and request.method == 'GET':
            flash(f'Lưu ý: Sản phẩm "{product.name}" chỉ còn {product.stock} cái.', 'warning')

        subtotal = product.price * quantity
        total_price += subtotal
        items_for_display.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

    # 3. Khởi tạo Form và điền dữ liệu cũ (nếu đã đăng nhập)
    form = CheckoutForm()
    if request.method == 'GET' and current_user.is_authenticated:
        form.full_name.data = current_user.full_name or ''
        form.email.data = current_user.email or ''
        form.phone.data = current_user.phone or ''
        # Điền địa chỉ cũ vào ô "chi tiết" (tạm thời)
        form.specific_address.data = current_user.address or ''

    # ==================================================================
    # PHẦN 2: XỬ LÝ KHI NGƯỜI DÙNG BẤM "HOÀN TẤT" (POST)
    # ==================================================================
    if form.validate_on_submit():

        # --- BƯỚC A: KIỂM TRA LẠI GIÁ TRỊ ĐƠN HÀNG (SECURITY CHECK) ---
        items_to_order = []
        total_price_check = 0

        for product in products_in_cart:
            product_id_str = str(product.id)
            quantity = cart[product_id_str]

            # Kiểm tra tồn kho nghiêm ngặt (Chặn đứng nếu hết hàng)
            if quantity > product.stock:
                flash(f'Sản phẩm "{product.name}" chỉ còn {product.stock} cái. Vui lòng cập nhật giỏ hàng.', 'danger')
                return redirect(url_for('main.view_cart'))

            subtotal = product.price * quantity
            total_price_check += subtotal
            items_to_order.append({
                'product_obj': product,
                'quantity': quantity,
                'price_at_purchase': product.price
            })

        # Chống hack: Đảm bảo giá client gửi lên khớp với giá server tính
        if total_price != total_price_check:
            flash('Dữ liệu giá không đồng bộ, vui lòng thử lại.', 'danger')
            return redirect(url_for('main.view_cart'))

        # --- BƯỚC B: TÍNH PHÍ VẬN CHUYỂN (SHIPPING FEE) ---
        shipping_fee = 0
        SHOP_LOCATION = 'Thành phố Hà Nội'  # Cấu hình vị trí shop
        user_province = form.province.data

        # Logic Freeship: Đơn hàng >= 1 triệu -> Miễn phí
        if total_price_check >= 1000000:
            shipping_fee = 0
        else:
            # Nếu cùng tỉnh -> 20k, khác tỉnh -> 35k
            if user_province == SHOP_LOCATION:
                shipping_fee = 20000
            else:
                shipping_fee = 35000

        # --- BƯỚC C: TÍNH MÃ GIẢM GIÁ (COUPON) ---
        discount_amount = 0
        coupon_code = form.coupon_code.data

        if coupon_code:
            coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
            now = datetime.now()

            # 1. Kiểm tra mã hợp lệ
            if not coupon or not coupon.active or coupon.expiration_date < now:
                flash("Mã giảm giá không hợp lệ hoặc đã hết hạn.", 'danger')
                return redirect(url_for('main.view_cart'))  # Chặn

            # 2. Kiểm tra giá trị đơn tối thiểu
            if total_price_check < coupon.min_order_value:
                flash(f"Mã này chỉ áp dụng cho đơn từ {coupon.min_order_value:,.0f} đ.", 'danger')
                return redirect(url_for('main.view_cart'))  # Chặn

            # 3. Tính tiền giảm
            if coupon.discount_type == 'percent':
                discount_amount = total_price_check * (coupon.discount_value / 100)
            else:
                discount_amount = coupon.discount_value

            # Không cho phép giảm giá vượt quá tiền hàng
            if discount_amount > total_price_check:
                discount_amount = total_price_check

            flash(f"Áp dụng mã {coupon.code} thành công! Giảm {discount_amount:,.0f} đ", 'success')

        # --- BƯỚC D: TÍNH TỔNG TIỀN CUỐI CÙNG ---
        # Công thức: (Tiền hàng - Giảm giá) + Ship
        final_total_price = (total_price_check - discount_amount) + shipping_fee

        # --- BƯỚC E: LƯU VÀO DATABASE & THANH TOÁN ---
        try:
            # 1. Xử lý địa chỉ: Gộp 4 trường thành 1 chuỗi
            specific = form.specific_address.data or ""
            full_address = f"{specific}, {form.ward.data}, {form.district.data}, {form.province.data}"
            if full_address.startswith(", "): full_address = full_address[2:]

            # 2. Tạo đối tượng Order
            new_order = Order(
                total_price=final_total_price,  # Dùng giá cuối cùng
                shipping_fee=shipping_fee,  # Lưu phí ship
                customer_name=form.full_name.data,
                customer_email=form.email.data,
                customer_phone=form.phone.data,
                shipping_address=full_address,
                payment_method=form.payment_method.data
            )

            # 3. Gán User (nếu có) và Cập nhật hồ sơ
            if current_user.is_authenticated:
                new_order.customer = current_user
                current_user.full_name = form.full_name.data
                current_user.phone = form.phone.data
                current_user.address = full_address  # Lưu địa chỉ mới nhất vào hồ sơ
                db.session.add(current_user)

            # Add đơn hàng (chưa commit)
            db.session.add(new_order)

            # 4. RẼ NHÁNH THANH TOÁN

            # === TRƯỜNG HỢP: COD ===
            if new_order.payment_method == 'COD':
                new_order.status = 'Pending'

                # Tạo Item và TRỪ KHO ngay
                for item in items_to_order:
                    order_item = OrderItem(
                        quantity=item['quantity'],
                        price_at_purchase=item['price_at_purchase'],
                        order=new_order, product=item['product_obj']
                    )
                    db.session.add(order_item)
                    # Trừ kho
                    item['product_obj'].stock -= item['quantity']
                    db.session.add(item['product_obj'])

                db.session.commit()  # Lưu tất cả

                # Gửi email
                try:
                    send_order_confirmation_email(new_order)
                except Exception as e:
                    current_app.logger.error(f'Lỗi gửi email COD: {e}')

                # Dọn dẹp Session
                if is_buy_now:
                    session.pop('buy_now_cart', None)
                    session.pop('is_buy_now', None)
                else:
                    session.pop('cart', None)

                return redirect(url_for('main.order_complete', order_id=new_order.id))


            # === TRƯỜNG HỢP: VNPAY ===
            elif new_order.payment_method == 'VNPAY':
                new_order.status = 'Pending Payment'

                # Tạo Item nhưng KHÔNG TRỪ KHO (Chờ IPN)
                for item in items_to_order:
                    order_item = OrderItem(
                        quantity=item['quantity'],
                        price_at_purchase=item['price_at_purchase'],
                        order=new_order, product=item['product_obj']
                    )
                    db.session.add(order_item)

                db.session.commit()  # Lưu để lấy ID đơn hàng

                # Dọn dẹp Session
                if is_buy_now:
                    session.pop('buy_now_cart', None)
                    session.pop('is_buy_now', None)
                else:
                    session.pop('cart', None)

                # Tạo URL thanh toán
                ip_addr = request.remote_addr
                payment_url = get_vnpay_payment_url(
                    order_id=new_order.id,
                    total_price=final_total_price,  # Dùng giá cuối cùng
                    order_desc=f'Thanh toan don hang {new_order.id}',
                    ip_addr=ip_addr
                )

                return redirect(payment_url)

        except Exception as e:
            db.session.rollback()
            print(f"Lỗi Checkout: {e}")  # In lỗi ra console để debug
            flash(f'Đã xảy ra lỗi khi xử lý đơn hàng: {str(e)}', 'danger')
            return redirect(url_for('main.view_cart'))

    # ==================================================================
    # PHẦN 3: RENDER GIAO DIỆN (GET hoặc khi Form lỗi)
    # ==================================================================
    return render_template('checkout.html',
                           title='Thanh toán',
                           form=form,
                           items=items_for_display,
                           total_price=total_price)


# === 5. TRANG HOÀN TẤT ĐƠN HÀNG ===
@main.route('/order-complete/<int:order_id>')
def order_complete(order_id):
    # Ai cũng có thể xem trang này (Guest hoặc User)
    order = Order.query.get_or_404(order_id)

    # Lấy các items trong đơn hàng
    order_items = db.session.query(OrderItem).options(
        db.joinedload(OrderItem.product)  # Tối ưu query
    ).filter_by(order_id=order.id).all()

    return render_template('order_complete.html', order=order, items=order_items)


# Đổi <int:product_id> thành <string:slug>
@main.route('/product/<string:slug>', methods=['GET', 'POST'])
def product_detail(slug):
    # Tìm sản phẩm theo slug thay vì id
    product = Product.query.filter_by(slug=slug).first_or_404()
    form = ReviewForm()  # Tạo form đánh giá

    # Xử lý khi người dùng gửi đánh giá
    if form.validate_on_submit():
        # Kiểm tra xem user đã đăng nhập chưa
        if not current_user.is_authenticated:
            flash('Bạn cần đăng nhập để viết đánh giá.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        # Tạo review mới
        new_review = Review(
            rating=form.rating.data,
            comment=form.comment.data,
            author=current_user,  # Gán người viết là user hiện tại
            product=product  # Gán review cho sản phẩm này
        )
        db.session.add(new_review)
        db.session.commit()

        flash('Cảm ơn bạn đã gửi đánh giá!', 'success')
        # Redirect lại chính trang này để xóa form (Post-Redirect-Get pattern)
        return redirect(url_for('main.product_detail', slug=product.slug))

    # Tải tất cả review của sản phẩm này, mới nhất lên đầu
    # Dùng joinedload để tải 'author' (User) cùng lúc, tránh N+1 query
    reviews = Review.query.options(db.joinedload(Review.author)) \
        .filter_by(product_id=product.id) \
        .order_by(Review.timestamp.desc()) \
        .all()
    related_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id
    ).limit(4).all()
    return render_template('product_detail.html',
                           title=product.name,
                           product=product,
                           reviews=reviews,  # Gửi danh sách review ra template
                           form=form,
                           related_products=related_products)  # Gửi form ra template


@main.route('/search')
def search():
    # 1. Lấy tham số
    query_str = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'default')
    category_filter = request.args.get('category', 'all')
    price_range = request.args.get('price_range', 'all')

    if not query_str:
        return redirect(url_for('main.index'))

    categories = Category.query.all()

    # 2. Xây dựng truy vấn cơ sở (THÊM ĐIỀU KIỆN ACTIVE NGAY ĐẦU)
    search_term = f"%{query_str}%"

    results_query = Product.query.filter(Product.is_active == True).filter(
        db.or_(
            Product.name.ilike(search_term),
            Product.description.ilike(search_term)
        )
    )

    # 3. Áp dụng LỌC DANH MỤC
    if category_filter != 'all':
        try:
            results_query = results_query.filter(
                Product.category_id == int(category_filter)
            )
        except ValueError:
            pass

    # 4. Áp dụng LỌC GIÁ
    if price_range == 'under_500k':
        results_query = results_query.filter(Product.price < 500000)
    elif price_range == '500k_to_1m':
        results_query = results_query.filter(Product.price.between(500000, 1000000))
    elif price_range == 'over_1m':
        results_query = results_query.filter(Product.price > 1000000)

    # 5. Áp dụng SẮP XẾP
    if sort_by == 'price_asc':
        results_query = results_query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        results_query = results_query.order_by(Product.price.desc())
    else:
        results_query = results_query.order_by(Product.name.asc())

    # 6. Lấy kết quả
    results = results_query.all()

    return render_template('search_results.html',
                           products=results,
                           query=query_str,
                           categories=categories,
                           current_sort=sort_by,
                           current_category=category_filter,
                           current_price=price_range)


@main.route('/category/<int:category_id>')
def category_products(category_id):
    # 1. Lấy danh mục
    category = Category.query.get_or_404(category_id)

    # 2. Lấy tất cả sản phẩm thuộc danh mục (CHỈ LẤY ACTIVE)
    # Lưu ý: category.products là query object (do lazy='dynamic')
    products = category.products.filter(Product.is_active == True) \
        .order_by(Product.name.asc()) \
        .all()

    return render_template('category_products.html',
                           category=category,
                           products=products)


@main.route('/blog')
def blog_index():
    """Trang hiển thị danh sách tất cả bài viết (đã Phân trang)."""
    page = request.args.get('page', 1, type=int)

    # Hiển thị 5 bài viết mỗi trang (trang blog thường ít hơn)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=5, error_out=False
    )
    posts = pagination.items

    return render_template('blog_list.html',
                           title='Blog',
                           posts=posts,
                           pagination=pagination)  # <-- Gửi pagination


@main.route('/blog/<int:post_id>')
def blog_post(post_id):
    """Trang chi tiết một bài viết."""
    post = Post.query.get_or_404(post_id)
    return render_template('blog_post.html', title=post.title, post=post)


main.route('/account')


@main.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()

    if form.validate_on_submit():
        # 1. Xử lý ảnh Avatar nếu có upload
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            # Lưu ý: Bạn cần đảm bảo model User có cột avatar (hoặc image_file)
            # Nếu model bạn tên là image_file thì sửa dòng dưới thành: current_user.image_file = picture_file
            current_user.avatar = picture_file

            # 2. Cập nhật thông tin cá nhân
        current_user.full_name = form.full_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data

        db.session.commit()
        flash('Tài khoản của bạn đã được cập nhật!', 'success')
        return redirect(url_for('main.account'))

    elif request.method == 'GET':
        # 3. Điền sẵn dữ liệu cũ vào form khi mới mở trang
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.full_name.data = current_user.full_name
        form.phone.data = current_user.phone
        form.address.data = current_user.address

    # 4. Lấy danh sách đơn hàng của user (Mới nhất lên đầu)
    # Nếu chưa có model Order thì tạm thời để orders = []
    try:
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date_ordered.desc()).all()
    except:
        orders = []

    # QUAN TRỌNG: Phải truyền biến form=form sang template
    return render_template('account.html', title='Tài khoản',
                           form=form,
                           orders=orders)

@main.route('/account/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form_profile = UpdateAccountForm()
    form_pass = ChangePasswordForm()

    # --- XỬ LÝ FORM CẬP NHẬT THÔNG TIN ---
    if 'submit_profile' in request.form and form_profile.validate_on_submit():
        current_user.full_name = form_profile.full_name.data
        current_user.phone = form_profile.phone.data
        current_user.address = form_profile.address.data
        db.session.commit()
        flash('Thông tin cá nhân đã được cập nhật.', 'success')
        return redirect(url_for('main.profile'))

    # --- XỬ LÝ FORM ĐỔI MẬT KHẨU ---
    if 'submit_password' in request.form and form_pass.validate_on_submit():
        # 1. Kiểm tra mật khẩu cũ có đúng không
        if not current_user.check_password(form_pass.old_password.data):
            flash('Mật khẩu hiện tại không đúng.', 'danger')
        else:
            # 2. Đổi sang mật khẩu mới
            current_user.set_password(form_pass.new_password.data)
            db.session.commit()
            flash('Mật khẩu đã được thay đổi thành công!', 'success')
            return redirect(url_for('main.profile'))

    # --- ĐIỀN DỮ LIỆU CŨ VÀO FORM (KHI GET) ---
    if request.method == 'GET':
        form_profile.full_name.data = current_user.full_name
        form_profile.email.data = current_user.email
        form_profile.phone.data = current_user.phone
        form_profile.address.data = current_user.address

    return render_template('profile.html',
                           title='Hồ sơ cá nhân',
                           form_profile=form_profile,
                           form_pass=form_pass)


@main.route('/contact', methods=['GET', 'POST'])  # <-- Thêm 'methods'
def contact():
    """Trang Liên hệ (đã nâng cấp có Form)."""
    form = ContactForm()

    if form.validate_on_submit():
        # Lấy dữ liệu từ form
        new_msg = ContactMessage(
            name=form.name.data,
            email=form.email.data,
            subject=form.subject.data,
            message=form.message.data
        )
        # Lưu tin nhắn vào database
        db.session.add(new_msg)
        db.session.commit()

        flash('Cảm ơn bạn! Tin nhắn của bạn đã được gửi. Chúng tôi sẽ phản hồi sớm nhất có thể.', 'success')

        # Chuyển hướng về trang liên hệ (để xóa form, tránh submit lại)
        return redirect(url_for('main.contact'))

    # Nếu là GET request hoặc form có lỗi, chỉ hiển thị trang
    return render_template('contact.html', title='Liên hệ', form=form)


@main.route('/terms')
def terms():
    """Trang Điều khoản Dịch vụ."""
    return render_template('terms.html', title='Điều khoản & Điều kiện')


@main.route('/advice')
def advice():
    """Trang Tư vấn & FAQs."""
    return render_template('advice.html', title='Tư vấn & FAQs')


# chatbot
@main.route('/ask-ai', methods=['POST'])
def ask_ai():
    # 1. Lấy API key từ config
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'API key bị thiếu.'}), 500

    # 2. Cấu hình Gemini
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/gemini-pro-latest')
    except Exception as e:
        return jsonify({'error': f'Lỗi cấu hình AI: {str(e)}'}), 500

    # 3. Lấy câu hỏi từ JavaScript (JSON)
    data = request.get_json()
    user_question = data.get('question')
    if not user_question:
        return jsonify({'error': 'Không có câu hỏi.'}), 400

    # 4. "Huấn luyện" (Prompt Engineering) cho AI
    # Đây là phần rất quan trọng để AI biết nó là ai
    prompt = f"""
        Bạn là một trợ lý AI fitness ảo của shop 'Home Fit Pro'. 
        Nhiệm vụ của bạn là trả lời các câu hỏi chung về tập luyện, 
        dinh dưỡng, và lợi ích của các dụng cụ (như tạ, thảm yoga).

        QUAN TRỌNG:
        - KHÔNG được trả lời các câu hỏi về giá cả, tồn kho, hay trạng thái đơn hàng.
        - Nếu bị hỏi về những thứ đó, hãy lịch sự trả lời: 
          "Tôi là AI hỗ trợ fitness. Để xem giá cả hoặc tồn kho, 
          bạn vui lòng sử dụng thanh tìm kiếm hoặc xem trang sản phẩm. 
          Để kiểm tra đơn hàng, bạn vui lòng vào trang Tài khoản."
        - Giữ câu trả lời ngắn gọn, thân thiện và hữu ích.

        Bây giờ, hãy trả lời câu hỏi của khách: "{user_question}"
    """

    # 5. Gửi câu hỏi đến Gemini và nhận câu trả lời
    try:
        response = model.generate_content(prompt)
        ai_answer = response.text

    except Exception as e:
        ai_answer = f"Xin lỗi, tôi đang gặp lỗi kỹ thuật: {str(e)}"
        print("=" * 40)
        print(f"!!! LỖI TỪ API GEMINI: {e}")
        print("=" * 40)
        ai_answer = f"Xin lỗi, tôi đang gặp lỗi kỹ thuật (đã ghi log)."  # Báo cho user biết

    # 6. Trả câu trả lời về cho JavaScript
    return jsonify({'answer': ai_answer})


@main.route('/update-cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})

    # Lấy thông tin từ form
    try:
        product_id_str = str(request.form['product_id'])
        action = request.form.get('action', 'update')  # 'update' hoặc 'remove'
    except KeyError:
        flash('Yêu cầu không hợp lệ.', 'danger')
        return redirect(url_for('main.view_cart'))

    if product_id_str not in cart:
        flash('Sản phẩm không có trong giỏ hàng.', 'warning')
        return redirect(url_for('main.view_cart'))

    # XỬ LÝ NÚT XÓA
    if action == 'remove':
        cart.pop(product_id_str)  # Xóa sản phẩm khỏi cart dictionary
        flash('Đã xóa sản phẩm khỏi giỏ hàng.', 'success')

    # XỬ LÝ NÚT CẬP NHẬT
    elif action == 'update':
        try:
            new_quantity = int(request.form['quantity'])
        except (ValueError, KeyError):
            flash('Số lượng không hợp lệ.', 'danger')
            return redirect(url_for('main.view_cart'))

        if new_quantity <= 0:
            # Nếu người dùng cập nhật số lượng về 0, chúng ta cũng xóa
            cart.pop(product_id_str)
            flash('Đã xóa sản phẩm khỏi giỏ hàng.', 'success')
        else:
            # Kiểm tra tồn kho trước khi cập nhật
            product = Product.query.get(int(product_id_str))
            if new_quantity > product.stock:
                flash(f'Xin lỗi, chỉ còn {product.stock} sản phẩm "{product.name}".', 'warning')
                # Không cập nhật, chỉ tải lại trang
            else:
                cart[product_id_str] = new_quantity
                # flash('Đã cập nhật số lượng sản phẩm.', 'success')

    # Lưu lại giỏ hàng vào session
    session['cart'] = cart
    return redirect(url_for('main.view_cart'))


@main.route('/track-order', methods=['GET', 'POST'])
def track_order():
    """Trang tra cứu đơn hàng cho khách (cả guest và user)."""
    form = TrackOrderForm()

    if form.validate_on_submit():
        order_id = form.order_id.data
        email = form.email.data

        # Tìm đơn hàng dựa trên ID VÀ Email
        order = Order.query.filter_by(id=order_id, customer_email=email).first()

        if order:
            # Nếu tìm thấy, hiển thị trang chi tiết (dùng lại template order_complete)
            # Chúng ta cần tải các items của đơn hàng này
            order_items = db.session.query(OrderItem).options(
                db.joinedload(OrderItem.product)
            ).filter_by(order_id=order.id).all()

            flash('Đã tìm thấy đơn hàng của bạn.', 'success')
            return render_template('order_complete.html',
                                   order=order,
                                   items=order_items,
                                   title="Chi tiết Đơn hàng")
        else:
            # Nếu không tìm thấy
            flash('Không tìm thấy đơn hàng. Vui lòng kiểm tra lại Mã Đơn hàng và Email.', 'danger')
            return redirect(url_for('main.track_order'))

    # Nếu là GET request (lần đầu vào trang), chỉ hiển thị form
    return render_template('track_order.html',
                           title='Tra cứu Đơn hàng',
                           form=form)


# === THÊM 2 ROUTE MỚI CHO VNPAY ===

@main.route('/vnpay-return')
def vnpay_return():
    """
    Trang VNPay chuyển về sau khi khách thanh toán.
    Trang này CHỈ ĐỂ HIỂN THỊ, không xử lý logic nghiệp vụ.
    """
    # Lấy tất cả tham số VNPay trả về qua query string
    vnp_response_data = request.args.to_dict()

    # Xác thực chữ ký
    is_valid = validate_vnpay_response(vnp_response_data)

    if is_valid:
        # Lấy mã Response Code (vnp_ResponseCode)
        response_code = vnp_response_data.get('vnp_ResponseCode')
        order_id = vnp_response_data.get('vnp_TxnRef')

        if response_code == '00':
            # Thanh toán thành công (TẠM THỜI - IPN mới là xác nhận cuối)
            flash('Thanh toán thành công! Đang chờ xử lý...', 'success')
            # Chuyển về trang chi tiết (hoặc trang cảm ơn tùy chỉnh)
            return redirect(url_for('main.order_complete', order_id=order_id))
        else:
            # Thanh toán thất bại
            flash('Thanh toán thất bại. Vui lòng thử lại.', 'danger')
            return redirect(url_for('main.view_cart'))
    else:
        # Chữ ký không hợp lệ
        flash('Lỗi: Chữ ký phản hồi VNPay không hợp lệ.', 'danger')
        return redirect(url_for('main.index'))


@main.route('/vnpay-ipn', methods=['GET'])
def vnpay_ipn():
    """
    IPN (Instant Payment Notification) - VNPay gọi ngầm.
    Đây là nơi XÁC NHẬN CUỐI CÙNG và CẬP NHẬT DATABASE.
    """
    vnp_response_data = request.args.to_dict()

    # 1. Xác thực chữ ký
    is_valid = validate_vnpay_response(vnp_response_data)

    if not is_valid:
        # Trả về lỗi cho VNPay
        return jsonify({'RspCode': '97', 'Message': 'Invalid Signature'})

    try:
        # 2. Lấy các thông tin quan trọng
        order_id = vnp_response_data.get('vnp_TxnRef')
        vnp_amount = int(vnp_response_data.get('vnp_Amount')) / 100  # (Nhớ chia 100)
        vnp_response_code = vnp_response_data.get('vnp_ResponseCode')

        # 3. Tìm đơn hàng
        order = Order.query.filter_by(id=order_id).first()
        if not order:
            return jsonify({'RspCode': '01', 'Message': 'Order not found'})

        # 4. Kiểm tra số tiền
        if order.total_price != vnp_amount:
            return jsonify({'RspCode': '04', 'Message': 'Invalid Amount'})

        # 5. Kiểm tra trạng thái đơn hàng (tránh IPN gọi lặp)
        if order.status != 'Pending Payment':
            # Đơn hàng này đã được xử lý rồi
            return jsonify({'RspCode': '02', 'Message': 'Order already processed'})

        # 6. XỬ LÝ THANH TOÁN
        if vnp_response_code == '00':
            # Thanh toán THÀNH CÔNG
            order.status = 'Confirmed'  # Hoặc 'Processing'
            order.is_paid = True

            # === TIẾN HÀNH TRỪ KHO (CHỈ KHI IPN THÀNH CÔNG) ===
            for item in order.items:
                item.product.stock -= item.quantity
                db.session.add(item.product)

            db.session.commit()

            # (Gửi email xác nhận thanh toán thành công ở đây)
            try:
                send_order_confirmation_email(order)
            except Exception as e:
                current_app.logger.error(f'Lỗi gửi email IPN: {e}')

            # Trả về cho VNPay
            return jsonify({'RspCode': '00', 'Message': 'Confirm Success'})

        else:
            # Thanh toán THẤT BẠI
            order.status = 'Cancelled'
            db.session.commit()
            return jsonify({'RspCode': '99', 'Message': 'Payment Failed'})

    except Exception as e:
        current_app.logger.error(f'Lỗi IPN: {e}')
        return jsonify({'RspCode': '99', 'Message': 'Unknown error'})


@main.route('/about-us')
def about_us():
    """Trang Về chúng tôi."""
    return render_template('about.html', title='Về Home Fit Pro')


@main.route('/return-policy')
def return_policy():
    """Trang Chính sách đổi trả."""
    return render_template('return_policy.html', title='Chính sách Đổi trả')


@admin.route('/message/<int:message_id>')
@login_required
@admin_required
def message_detail(message_id):
    """Trang xem chi tiết 1 tin nhắn và đánh dấu là "Đã đọc"."""
    msg = ContactMessage.query.get_or_404(message_id)

    # Đánh dấu là đã đọc
    if not msg.is_read:
        msg.is_read = True
        db.session.commit()

    return render_template('admin/message_detail.html',
                           title=f'Tin nhắn: {msg.subject}',
                           message=msg)


@main.route('/buy-now/<int:product_id>', methods=['POST'])
def buy_now(product_id):
    # 1. KHÔNG đụng đến 'cart'. Tạo một giỏ hàng MUA NGAY riêng
    buy_now_cart = {}

    # 2. Lấy sản phẩm và số lượng (logic y hệt cũ)
    product = Product.query.get_or_404(product_id)
    product_id_str = str(product.id)

    try:
        quantity_to_add = int(request.form.get('quantity', '1'))
    except ValueError:
        quantity_to_add = 1
    if quantity_to_add <= 0:
        quantity_to_add = 1

    # 3. Kiểm tra tồn kho (y hệt cũ)
    if quantity_to_add > product.stock:
        flash(f'Xin lỗi, chỉ còn {product.stock} sản phẩm "{product.name}" trong kho.', 'warning')
        return redirect(request.referrer)

    # 4. Thêm 1 món hàng này vào giỏ MUA NGAY
    buy_now_cart[product_id_str] = quantity_to_add

    # 5. Lưu giỏ hàng MUA NGAY vào session
    session['buy_now_cart'] = buy_now_cart
    # Đặt 1 "cờ" (flag) để báo cho checkout biết đây là luồng Mua Ngay
    session['is_buy_now'] = True

    # 6. Chuyển hướng đến checkout. Giỏ hàng chính ('cart') vẫn an toàn.
    return redirect(url_for('main.checkout'))


@main.route('/wishlist')
@login_required
def view_wishlist():
    """Trang xem danh sách yêu thích."""
    # Lấy các sản phẩm trong wishlist của user hiện tại
    products = current_user.wishlist.all()
    return render_template('wishlist.html', title='Danh sách Yêu thích', products=products)


@main.route('/wishlist/toggle/<int:product_id>')
@login_required
def toggle_wishlist(product_id):
    """Thêm hoặc Xóa sản phẩm khỏi wishlist."""
    product = Product.query.get_or_404(product_id)

    # Kiểm tra xem sản phẩm đã có trong wishlist chưa
    # (Dùng query dynamic)
    if current_user.wishlist.filter_by(id=product.id).first():
        # Nếu có rồi -> Xóa
        current_user.wishlist.remove(product)
        # flash(f'Đã xóa "{product.name}" khỏi yêu thích.', 'info')
    else:
        # Nếu chưa có -> Thêm
        current_user.wishlist.append(product)
        # flash(f'Đã thêm "{product.name}" vào yêu thích.', 'success')

    db.session.commit()

    # Quay lại trang cũ
    return redirect(request.referrer or url_for('main.index'))


# === ROUTE SÀNG LỌC SỨC KHỎE (PAR-Q) ===
@main.route('/health-screening', methods=['GET', 'POST'])
@login_required  # Bắt buộc đăng nhập để lưu hồ sơ
def health_screening():
    form = ParqForm()

    if form.validate_on_submit():
        # Kiểm tra xem có bất kỳ câu nào là 'yes' không
        answers = [
            form.q1.data, form.q2.data, form.q3.data, form.q4.data,
            form.q5.data, form.q6.data, form.q7.data
        ]

        # Nếu 'yes' xuất hiện trong danh sách -> Có rủi ro
        has_risk = 'yes' in answers

        # Lưu vào database
        screening = HealthScreening(
            user_id=current_user.id,
            q1=(form.q1.data == 'yes'),
            q2=(form.q2.data == 'yes'),
            q3=(form.q3.data == 'yes'),
            q4=(form.q4.data == 'yes'),
            q5=(form.q5.data == 'yes'),
            q6=(form.q6.data == 'yes'),
            q7=(form.q7.data == 'yes'),
            risk_detected=has_risk
        )
        db.session.add(screening)
        db.session.commit()

        # Chuyển hướng đến trang kết quả
        return redirect(url_for('main.health_result', result_id=screening.id))

    if request.method == 'POST':
        print("=" * 30)

        print("!!! POST REQUEST FAILED VALIDATION !!!")

        print(f"Form Data nhận được: {request.form}")

        print(f"Lỗi cụ thể (Errors): {form.errors}")

        print("=" * 30)
    return render_template('health_screening.html', title='Sàng lọc Sức khỏe (PAR-Q)', form=form)


@main.route('/health-result/<int:result_id>')
@login_required
def health_result(result_id):
    """Trang hiển thị kết quả (Safe hoặc Warning)."""
    result = HealthScreening.query.get_or_404(result_id)

    # Bảo mật: Chỉ xem được kết quả của chính mình
    if result.user_id != current_user.id and current_user.role.name != 'Admin':
        flash('Bạn không có quyền xem kết quả này.', 'danger')
        return redirect(url_for('main.index'))

    return render_template('health_result.html', title='Kết quả Sàng lọc', result=result)


@main.route('/consultation/needs', methods=['GET', 'POST'])
def needs_assessment():
    form = NeedsAssessmentForm()

    # Xử lý khi có Request POST (AJAX gửi lên)
    if request.method == 'POST' and form.validate_on_submit():
        # 1. Lấy dữ liệu từ form
        goal = form.goal.data
        space = form.space.data
        budget = form.budget.data
        experience = form.experience.data

        # 2. Logic lọc sản phẩm (Copy từ hàm recommendation cũ sang)
        query = Product.query.join(Product.category).filter(Product.is_active == True)

        # --- Logic Goal ---
        if goal == 'lose_weight' or goal == 'health':
            query = query.filter(db.or_(Category.name.ilike('%máy%'), Category.name.ilike('%xe đạp%'),
                                        Category.name.ilike('%dây nhảy%')))
        elif goal == 'gain_muscle':
            query = query.filter(
                db.or_(Category.name.ilike('%tạ%'), Category.name.ilike('%giàn%'), Category.name.ilike('%ghế%')))
        elif goal == 'recovery':
            query = query.filter(
                db.or_(Category.name.ilike('%thảm%'), Category.name.ilike('%yoga%'), Category.name.ilike('%roller%')))

        # --- Logic Space ---
        if space == 'small':
            query = query.filter(~Category.name.ilike('%giàn tạ%'), ~Category.name.ilike('%máy chạy%'))

        # --- Logic Experience ---
        if experience == 'newbie':
            # Ví dụ logic cho newbie
            pass

            # --- Logic Budget ---
        if budget == 'low':
            query = query.filter(Product.price < 1000000)
        elif budget == 'medium':
            query = query.filter(Product.price.between(1000000, 5000000))
        elif budget == 'high':
            query = query.filter(Product.price > 5000000)

        # Lấy kết quả
        products = query.limit(6).all()

        # Fallback: Nếu không tìm thấy, lấy 4 sản phẩm ngẫu nhiên
        if not products:
            products = Product.query.filter(Product.is_active == True).limit(4).all()

        # 3. Chuyển đổi dữ liệu thành JSON để gửi về cho Javascript
        products_data = []
        for p in products:
            # Xử lý ảnh (để JS hiển thị đúng)
            img_src = p.image_url
            if not img_src.startswith('http'):
                img_src = url_for('static', filename=img_src)

            products_data.append({
                'id': p.id,
                'name': p.name,
                'price': p.price,
                'image': img_src,
                'slug': p.slug,
                'category': p.category.name if p.category else ''
            })

        return jsonify({'status': 'success', 'products': products_data})

    return render_template('consultation/needs.html', title='Đánh giá Nhu cầu', form=form)


# === BƯỚC 3: TRANG GỢI Ý SẢN PHẨM ===
@main.route('/consultation/recommendation')
# @login_required
def recommendation():
    goal = request.args.get('goal')
    space = request.args.get('space')
    budget = request.args.get('budget')

    # --- LOGIC GỢI Ý (ALGORITHM) ---
    query = Product.query

    # 1. Lọc theo NGÂN SÁCH
    if budget == 'low':
        query = query.filter(Product.price < 1000000)
    elif budget == 'medium':
        query = query.filter(Product.price.between(1000000, 5000000))
    elif budget == 'high':
        query = query.filter(Product.price > 5000000)

    # 2. Lọc theo KHÔNG GIAN (Dùng tên danh mục để lọc tương đối)
    # Chúng ta giả định admin đặt tên danh mục có chứa các từ khóa này
    if space == 'small':
        # Nhà nhỏ: Chỉ lấy Tạ, Dây, Thảm, Phụ kiện (Tránh máy to)
        # Dùng NOT ILIKE để loại trừ máy to
        query = query.filter(
            ~Product.name.ilike('%máy chạy%'),
            ~Product.name.ilike('%giàn tạ%'),
            ~Product.name.ilike('%xe đạp%')
        )

    # 3. Lọc theo MỤC TIÊU
    if goal == 'recovery':
        # Ưu tiên Yoga, Foam roller
        query = query.filter(
            db.or_(
                Product.name.ilike('%yoga%'),
                Product.name.ilike('%thảm%'),
                Product.name.ilike('%roller%'),
                Product.description.ilike('%phục hồi%')
            )
        )
    elif goal == 'gain_muscle':
        # Ưu tiên Tạ
        query = query.filter(Product.name.ilike('%tạ%'))

    # Lấy kết quả (tối đa 6 món tốt nhất)
    suggested_products = query.limit(6).all()

    # Nếu không tìm thấy gì (do lọc quá kỹ), lấy random vài món "Best Seller" để lấp vào
    if not suggested_products:
        suggested_products = Product.query.limit(4).all()
        flash('Chúng tôi không tìm thấy sản phẩm khớp 100% tiêu chí, nhưng đây là các gợi ý phổ biến:', 'info')

    return render_template('consultation/recommendation.html',
                           title='Gợi ý cho bạn',
                           products=suggested_products)


@main.route('/force-fix-db')
def force_fix_db():
    try:
        # 1. Kiểm tra tổng số sản phẩm hiện có
        total_products = Product.query.count()

        # 2. Cưỡng chế UPDATE toàn bộ bảng trong SQL (bất kể giá trị cũ là gì)
        # Lệnh này tương đương: UPDATE products SET is_active = 1;
        rows_updated = Product.query.update({Product.is_active: True})

        db.session.commit()

        return f"""
        <h1>Báo cáo sửa lỗi:</h1>
        <ul>
            <li>Tổng số sản phẩm trong kho: <strong>{total_products}</strong></li>
            <li>Số dòng đã được 'ép' bật Active: <strong>{rows_updated}</strong></li>
        </ul>
        <p>Bây giờ hãy quay lại <a href="/">Trang chủ</a> để kiểm tra.</p>
        """
    except Exception as e:
        db.session.rollback()
        return f"Lỗi: {str(e)}"


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext

    # Lưu vào thư mục static/profile_pics
    picture_path = os.path.join(current_app.root_path, 'static/profile_pics', picture_fn)

    # Tạo thư mục nếu chưa có
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)

    form_picture.save(picture_path)
    return picture_fn