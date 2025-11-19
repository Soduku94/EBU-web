from flask import render_template, session, redirect, url_for, flash, request
from flask_login import current_user, login_required
from datetime import datetime
import google.generativeai as genai
from flask import current_app, jsonify

from . import main
from .forms import CheckoutForm, ReviewForm  # Import form checkout chúng ta vừa định nghĩa
from app.models import Product, Category, Order, OrderItem, Review, Post
from app.extensions import db
from app.email import send_order_confirmation_email
from app.models import Order
from .forms import TrackOrderForm
from flask import render_template, request, flash, redirect, url_for  # Đảm bảo đã import

from app.vnpay_service import get_vnpay_payment_url, validate_vnpay_response


from .forms import ContactForm
from app.models import ContactMessage
from app.extensions import db



from app.models import ContactMessage
from ..admin import admin
from ...decorators import admin_required


@main.route('/')
@main.route('/index')
def index():
    featured_products = Product.query.order_by(Product.id.desc()).limit(8).all()
    categories = Category.query.all()
    latest_posts = Post.query.order_by(Post.timestamp.desc()).limit(2).all()

    # === THÊM DÒNG NÀY VÀO ===
    # Lấy 3 đánh giá 5 SAO mới nhất
    # Tải kèm (joinedload) Tác giả và Sản phẩm để tránh N+1 query
    latest_reviews = Review.query.options(
        db.joinedload(Review.author),
        db.joinedload(Review.product)
    ) \
        .filter_by(rating=5) \
        .order_by(Review.timestamp.desc()) \
        .limit(3).all()
    # ==========================

    return render_template('index.html',
                           products=featured_products,
                           categories=categories,
                           latest_posts=latest_posts,
                           latest_reviews=latest_reviews)  # <-- Gửi reviews ra template


# === 2. THÊM VÀO GIỎ HÀNG (DÙNG SESSION) ===
@main.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    # 1. Lấy giỏ hàng từ session
    cart = session.get('cart', {})

    # 2. Lấy sản phẩm
    product = Product.query.get_or_404(product_id)
    product_id_str = str(product.id)  # Session keys phải là string

    # 3. Lấy số lượng từ form
    # Dùng .get('quantity', '1') để lấy, nếu không có (từ trang chủ) thì mặc định là '1'
    # Dùng int() để chuyển sang số nguyên
    try:
        quantity_to_add = int(request.form.get('quantity', '1'))
    except ValueError:
        quantity_to_add = 1  # Nếu ai đó cố tình nhập chữ, mặc định là 1

    # Đảm bảo số lượng luôn là số dương
    if quantity_to_add <= 0:
        quantity_to_add = 1

    # 4. Kiểm tra tồn kho
    current_quantity_in_cart = cart.get(product_id_str, 0)

    # Kiểm tra xem tổng số lượng (trong giỏ + sắp thêm) có vượt kho không
    if current_quantity_in_cart + quantity_to_add > product.stock:
        flash(
            f'Xin lỗi, bạn chỉ có thể thêm tối đa {product.stock - current_quantity_in_cart} sản phẩm "{product.name}" nữa.',
            'warning')
        return redirect(request.referrer or url_for('main.index'))

    # 5. Thêm vào giỏ
    if product_id_str in cart:
        cart[product_id_str] += quantity_to_add
    else:
        cart[product_id_str] = quantity_to_add

    # 6. Lưu lại session
    session['cart'] = cart

    flash(f'Đã thêm {product.name} vào giỏ hàng!', 'success')
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
    # === PHẦN 1: KIỂM TRA GIỎ HÀNG (LUỒNG "MUA NGAY" HOẶC "GIỎ HÀNG") ===
    # ---------------------------------------------------------------
    # Kiểm tra xem người dùng có đang ở luồng "Mua Ngay" (từ trang chi tiết) không
    is_buy_now = session.get('is_buy_now', False)

    if is_buy_now:
        # Nếu là luồng Mua Ngay, dùng giỏ hàng tạm thời
        cart = session.get('buy_now_cart', {})
    else:
        # Nếu là luồng Giỏ hàng bình thường, dùng giỏ hàng chính
        cart = session.get('cart', {})

    # Nếu không có giỏ hàng nào (rỗng), quay về trang chủ
    if not cart:
        flash('Giỏ hàng của bạn đang rỗng.', 'info')
        return redirect(url_for('main.index'))

    # === PHẦN 2: TÍNH TOÁN DỮ LIỆU HIỂN THỊ (CHO GET REQUEST) ===
    # ----------------------------------------------------------
    # (Dùng để hiển thị "Tóm tắt đơn hàng" bên phải, chạy ngay cả khi GET)

    product_ids = [int(pid) for pid in cart.keys()]
    products_in_cart = Product.query.filter(Product.id.in_(product_ids)).all()

    items_for_display = []  # Danh sách để gửi ra template
    total_price = 0  # Tổng tiền để gửi ra template

    for product in products_in_cart:
        product_id_str = str(product.id)
        quantity = cart[product_id_str]

        # Nếu là GET request, cảnh báo nếu kho không đủ
        if quantity > product.stock and request.method == 'GET':
            flash(f'Lưu ý: Sản phẩm "{product.name}" chỉ còn {product.stock} cái.', 'warning')

        subtotal = product.price * quantity
        total_price += subtotal
        items_for_display.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })

    # === PHẦN 3: KHỞI TẠO FORM VÀ XỬ LÝ GET ===
    # -----------------------------------------------
    form = CheckoutForm()

    # Tự động điền form nếu user đã đăng nhập (chỉ khi là GET)
    if request.method == 'GET' and current_user.is_authenticated:
        form.full_name.data = current_user.full_name or ''
        form.email.data = current_user.email or ''
        form.phone.data = current_user.phone or ''
        form.shipping_address.data = current_user.address or ''

    # === PHẦN 4: XỬ LÝ KHI NGƯỜI DÙNG NHẤN "HOÀN TẤT ĐƠN HÀNG" (POST) ===
    # ----------------------------------------------------------------------
    if form.validate_on_submit():

        # --- 4a. Kiểm tra Server-side (Bảo mật) ---
        # (Tính toán lại tổng tiền và kiểm tra kho lần cuối
        #  để đảm bảo không bị thay đổi ở phía client)

        items_to_order = []
        total_price_check = 0

        # Dùng lại 'products_in_cart' (đã tải ở Phần 2) cho hiệu quả
        for product in products_in_cart:
            product_id_str = str(product.id)
            quantity = cart[product_id_str]

            # Kiểm tra chặn (nghiêm ngặt)
            if quantity > product.stock:
                flash(f'Sản phẩm "{product.name}" chỉ còn {product.stock} cái. Vui lòng quay lại giỏ hàng.', 'danger')
                return redirect(url_for('main.view_cart'))  # Quay về giỏ hàng (không phải checkout)

            subtotal = product.price * quantity
            total_price_check += subtotal
            items_to_order.append({
                'product_obj': product,
                'quantity': quantity,
                'price_at_purchase': product.price
            })

        # Đảm bảo giá không bị thay đổi (tổng tiền lúc GET và POST phải khớp)
        if total_price != total_price_check:
            flash('Đã có lỗi xảy ra với tổng tiền, vui lòng thử lại.', 'danger')
            return redirect(url_for('main.view_cart'))

        # --- 4b. Bắt đầu Giao dịch Database (Tạo Đơn hàng) ---
        try:
            # 1. Tạo đối tượng Order
            new_order = Order(
                total_price=total_price_check,  # Dùng giá đã kiểm tra
                customer_name=form.full_name.data,
                customer_email=form.email.data,
                customer_phone=form.phone.data,
                shipping_address=form.shipping_address.data,
                payment_method=form.payment_method.data
            )

            # 2. Gán User (nếu đã đăng nhập)
            if current_user.is_authenticated:
                new_order.customer = current_user
                # Cập nhật thông tin profile cho user
                current_user.full_name = form.full_name.data
                current_user.phone = form.phone.data
                current_user.address = form.shipping_address.data
                db.session.add(current_user)

            # Add đơn hàng (new_order) vào session
            db.session.add(new_order)

            # --- 4c. Rẽ nhánh xử lý COD / VNPAY ---

            if new_order.payment_method == 'COD':
                # --- Xử lý COD ---
                new_order.status = 'Pending'  # Trạng thái chờ xử lý

                # TẠO OrderItem VÀ TRỪ KHO
                for item in items_to_order:
                    product_to_update = item['product_obj']
                    order_item = OrderItem(
                        quantity=item['quantity'],
                        price_at_purchase=item['price_at_purchase'],
                        order=new_order, product=product_to_update
                    )
                    db.session.add(order_item)

                    product_to_update.stock -= item['quantity']
                    db.session.add(product_to_update)

                # Commit và gửi email
                db.session.commit()
                try:
                    send_order_confirmation_email(new_order)
                except Exception as e:
                    current_app.logger.error(f'Lỗi gửi email COD: {e}')

                # *** SỬA LỖI LOGIC DỌN DẸP SESSION ***
                if is_buy_now:
                    session.pop('buy_now_cart', None)
                    session.pop('is_buy_now', None)
                else:
                    session.pop('cart', None)

                # CHUYỂN HƯỚNG
                return redirect(url_for('main.order_complete', order_id=new_order.id))


            elif new_order.payment_method == 'VNPAY':
                # --- Xử lý VNPAY ---
                new_order.status = 'Pending Payment'  # Trạng thái chờ thanh toán

                # CHỈ TẠO OrderItem, KHÔNG TRỪ KHO
                for item in items_to_order:
                    product_to_update = item['product_obj']
                    order_item = OrderItem(
                        quantity=item['quantity'],
                        price_at_purchase=item['price_at_purchase'],
                        order=new_order, product=product_to_update
                    )
                    db.session.add(order_item)

                # Commit để lấy new_order.id
                db.session.commit()

                # *** DỌN DẸP SESSION (Code cũ của bạn đã đúng) ***
                if is_buy_now:
                    session.pop('buy_now_cart', None)
                    session.pop('is_buy_now', None)
                else:
                    session.pop('cart', None)

                # Lấy IP của khách (quan trọng cho VNPay)
                ip_addr = request.remote_addr

                # Tạo URL VNPay
                payment_url = get_vnpay_payment_url(
                    order_id=new_order.id,
                    total_price=new_order.total_price,
                    order_desc=f'Thanh toan don hang {new_order.id}',
                    ip_addr=ip_addr
                )

                # CHUYỂN HƯỚNG
                return redirect(payment_url)

        except Exception as e:
            db.session.rollback()
            flash(f'Đã xảy ra lỗi khi đặt hàng: {str(e)}', 'danger')
            return redirect(url_for('main.view_cart'))

    # === PHẦN 5: RENDER TRANG (CHO GET REQUEST) ===
    # ------------------------------------------------
    # (Nếu không phải POST, hoặc nếu form validate thất bại)
    return render_template('checkout.html',
                           title='Thanh toán',
                           form=form,
                           items=items_for_display,  # Gửi tóm tắt đơn hàng
                           total_price=total_price)  # Gửi tổng tiền

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



@main.route('/product/<int:product_id>', methods=['GET', 'POST'])  # <-- Thêm methods
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
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
        return redirect(url_for('main.product_detail', product_id=product.id))

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
    # 1. Lấy tất cả tham số từ URL
    query_str = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'default')
    category_filter = request.args.get('category', 'all')
    price_range = request.args.get('price_range', 'all')

    if not query_str:
        return redirect(url_for('main.index'))

    # 2. Lấy danh sách danh mục (để hiển thị trong bộ lọc)
    categories = Category.query.all()

    # 3. Xây dựng truy vấn (Query) cơ sở
    search_term = f"%{query_str}%"
    results_query = Product.query.filter(
        db.or_(
            Product.name.ilike(search_term),
            Product.description.ilike(search_term)
        )
    )

    # 4. Áp dụng LỌC DANH MỤC (nếu có)
    if category_filter != 'all':
        try:
            # Thêm bộ lọc .filter() vào query
            results_query = results_query.filter(
                Product.category_id == int(category_filter)
            )
        except ValueError:
            pass  # Bỏ qua nếu 'category' không phải là số

    # 5. Áp dụng LỌC GIÁ (nếu có)
    if price_range == 'under_500k':
        results_query = results_query.filter(Product.price < 500000)
    elif price_range == '500k_to_1m':
        results_query = results_query.filter(Product.price.between(500000, 1000000))
    elif price_range == 'over_1m':
        results_query = results_query.filter(Product.price > 1000000)

    # 6. Áp dụng SẮP XẾP (luôn ở cuối cùng)
    if sort_by == 'price_asc':
        results_query = results_query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        results_query = results_query.order_by(Product.price.desc())
    else:
        results_query = results_query.order_by(Product.name.asc())

    # 7. Lấy kết quả cuối cùng
    results = results_query.all()

    # 8. Render, gửi tất cả giá trị hiện tại ra template
    return render_template('search_results.html',
                           products=results,
                           query=query_str,
                           categories=categories,
                           current_sort=sort_by,
                           current_category=category_filter,
                           current_price=price_range
                           )


# === THÊM ROUTE MỚI: LỌC SẢN PHẨM THEO DANH MỤC ===
@main.route('/category/<int:category_id>')
def category_products(category_id):
    # 1. Lấy danh mục, nếu không tìm thấy sẽ tự động 404
    category = Category.query.get_or_404(category_id)

    # 2. Lấy tất cả sản phẩm thuộc danh mục đó
    # (Vì relationship 'products' trong model Category là lazy='dynamic',
    # chúng ta có thể dùng .order_by và .all() như một query)
    products = category.products.order_by(Product.name.asc()).all()

    # 3. Render template mới, gửi category và products ra
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
                           pagination=pagination) # <-- Gửi pagination

@main.route('/blog/<int:post_id>')
def blog_post(post_id):
    """Trang chi tiết một bài viết."""
    post = Post.query.get_or_404(post_id)
    return render_template('blog_post.html', title=post.title, post=post)


main.route('/account')


@main.route('/account')
@login_required  # Chỉ người đã đăng nhập mới vào được
def account():
    """Trang xem lịch sử đơn hàng của user."""
    # Lấy tất cả đơn hàng của user hiện tại, sắp xếp mới nhất lên đầu
    orders = Order.query.filter_by(customer=current_user) \
        .order_by(Order.order_date.desc()) \
        .all()

    return render_template('account.html',
                           title='Tài khoản của tôi',
                           orders=orders)


@main.route('/contact', methods=['GET', 'POST']) # <-- Thêm 'methods'
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
                flash('Đã cập nhật số lượng sản phẩm.', 'success')

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

@main.route('/test-500')
def test_error():
    # Cố tình chia cho 0 để gây lỗi
    return 1 / 0


