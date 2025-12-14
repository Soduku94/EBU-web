from flask import render_template, redirect, url_for, flash, request
from flask_bcrypt import generate_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from .forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from app.email import send_password_reset_email
import secrets
from . import auth
from .forms import LoginForm, RegistrationForm
from app.models import User, Role
from app.extensions import db

from werkzeug.security import generate_password_hash, check_password_hash
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        # Tìm user bằng EMAIL
        user = User.query.filter_by(email=form.email.data).first()

        # Kiểm tra mật khẩu
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Đăng nhập thất bại. Vui lòng kiểm tra Email và Mật khẩu.', 'danger')

    return render_template('auth/login.html', title='Đăng nhập', form=form)

@auth.route('/logout')
@login_required
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
        hashed_password = generate_password_hash(form.password.data)

        # Lấy Role User
        role = Role.query.filter_by(name='User').first()
        if not role:
            role = Role(name='User')
            db.session.add(role)
            db.session.commit()

        # --- KỸ THUẬT TỰ TẠO USERNAME ---
        # Lấy phần trước @ của email (ví dụ: dung.vu@...) -> dung.vu
        base_name = form.email.data.split('@')[0]
        # Thêm chuỗi ngẫu nhiên để đảm bảo không trùng (ví dụ: dung.vu_a1b2)
        auto_username = f"{base_name}_{secrets.token_hex(3)}"

        # Tạo User
        user = User(
            username=auto_username,  # Username tự sinh (User không cần biết cái này)
            email=form.email.data,
            password_hash=hashed_password,
            full_name=form.full_name.data,
            role=role
            # is_active bỏ đi như yêu cầu trước
        )

        db.session.add(user)
        db.session.commit()

        flash('Đăng ký thành công! Hãy đăng nhập bằng Email của bạn.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', title='Đăng ký', form=form)




@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Trang nhập email để yêu cầu reset."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)

        # Luôn thông báo thành công để tránh lộ thông tin user (security best practice)
        flash('Kiểm tra email của bạn để được hướng dẫn đặt lại mật khẩu.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html', title='Quên mật khẩu', form=form)


@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Trang nhập mật khẩu mới (sau khi click link email)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.verify_reset_token(token)
    if not user:
        flash('Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('main.index'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Mật khẩu của bạn đã được đặt lại thành công.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', title='Đặt lại mật khẩu', form=form)
