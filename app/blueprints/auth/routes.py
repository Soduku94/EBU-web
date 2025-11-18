from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from . import auth
from .forms import LoginForm, RegistrationForm
from app.models import User, Role
from app.extensions import db


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu user đã đăng nhập, ném về trang chủ
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        # Tìm user trong database
        user = User.query.filter_by(email=form.email.data).first()

        # Kiểm tra user và mật khẩu
        if user is not None and user.check_password(form.password.data):
            # Đăng nhập user
            login_user(user, remember=form.remember_me.data)
            flash('Đăng nhập thành công!', 'success')

            # Lấy trang mà user muốn truy cập trước đó (nếu có)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                if user.role.name == 'Admin':
                    next_page = url_for('admin.index')  # Admin về Dashboard
                else:
                    next_page = url_for('main.index')  # Khách về Trang chủ
            return redirect(next_page)

        flash('Email hoặc mật khẩu không đúng.', 'danger')

    # Nếu là GET request hoặc validate fail, hiển thị form
    return render_template('auth/login.html', title='Đăng nhập', form=form)


@auth.route('/logout')
@login_required  # Chỉ user đã đăng nhập mới thấy nút này
def logout():
    logout_user()
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Lấy role 'Customer' (khách hàng)
        customer_role = Role.query.filter_by(name='Customer').first()
        if customer_role is None:
            # Xử lý lỗi nếu database chưa được seed (dù chúng ta đã làm)
            flash('Lỗi hệ thống: Không tìm thấy vai trò Customer.', 'danger')
            return redirect(url_for('main.index'))

        # Tạo user mới
        user = User(username=form.username.data,
                    email=form.email.data,
                    role=customer_role)  # Mặc định là Customer
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('Chúc mừng, bạn đã đăng ký tài khoản thành công!', 'success')
        # Tự động đăng nhập user sau khi đăng ký
        login_user(user)
        return redirect(url_for('main.index'))  # Chuyển về trang chủ

    return render_template('auth/register.html', title='Đăng ký', form=form)