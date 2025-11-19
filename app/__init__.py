from flask import Flask,session, render_template

from config import config
from .extensions import db, migrate, login_manager,ckeditor,mail




def create_app(config_name='default'):
    """
    Hàm khởi tạo ứng dụng (Application Factory).
    """
    app = Flask(__name__)

    # 1. Tải cấu hình
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 2. Khởi tạo Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    ckeditor.init_app(app)

    mail.init_app(app)
    # 3. Đăng ký Blueprints
    # (Tạm thời import ở đây để tránh lỗi 'circular import')

    # Blueprint cho 'main' (trang chủ, v.v.)
    from .blueprints.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Blueprint cho 'auth' (đăng nhập, đăng ký)
    # (Chúng ta sẽ code chi tiết sau)
    from .blueprints.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .blueprints.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')  # Đặt tiền tố /admin
    # lỗi
    register_error_handlers(app)
    @app.context_processor
    def inject_cart_count():
        cart = session.get('cart', {})
        count = sum(cart.values())  # Tính tổng số lượng các món hàng
        return dict(cart_count=count)




    return app


def register_error_handlers(app):
    @app.errorhandler(404)
    def page_not_found(e):
        # Trả về template 404 và mã lỗi 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        # Trả về template 500 và mã lỗi 500
        return render_template('errors/500.html'), 500