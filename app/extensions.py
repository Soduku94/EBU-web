from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_ckeditor import CKEditor
from flask_mail import Mail
# Khởi tạo các đối tượng
db = SQLAlchemy()
migrate = Migrate()

# Cấu hình cho Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Tên blueprints.route (sẽ tạo sau)
login_manager.login_message = 'Bạn cần đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'info' # Dùng cho category của flash message

ckeditor = CKEditor()
# khởi tạp đối tượng mai

mail = Mail()

