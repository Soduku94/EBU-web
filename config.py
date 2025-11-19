import os
from dotenv import load_dotenv

# Xác định thư mục gốc của dự án
basedir = os.path.abspath(os.path.dirname(__file__))
# Tải các biến môi trường từ file .env
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Lớp cấu hình cơ sở."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ban-phai-thay-doi-key-nay-neu-quen-set-env'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    #============================================
    #đây là config mấy cái key
    # cái này để Flask đọc được api key
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # cái này để ứng dung đọc được cấu hình mail của chúng ta
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    #=============================================

    # === THÊM CẤU HÌNH VNPAY ===
    VNPAY_TMN_CODE = os.environ.get('VNPAY_TMN_CODE')
    VNPAY_HASH_SECRET = os.environ.get('VNPAY_HASH_SECRET')
    VNPAY_PAYMENT_URL = os.environ.get('VNPAY_PAYMENT_URL')
    VNPAY_RETURN_URL = os.environ.get('VNPAY_RETURN_URL')
    VNPAY_IPN_URL = os.environ.get('VNPAY_IPN_URL')
#cấu hình đường dẫn lưu ảnh sản phẩm
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    # Định nghĩa các đuôi file ảnh cho phép
    UPLOAD_EXTENSIONS = ['.jpg', '.png', '.gif', '.jpeg']
    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    """Cấu hình cho môi trường phát triển."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'dev-db.sqlite')  # Dự phòng nếu .env bị thiếu


class ProductionConfig(Config):
    """Cấu hình cho môi trường sản phẩm (production)."""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')  # Sẽ lấy từ dịch vụ hosting


# Dictionary để lựa chọn config
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
