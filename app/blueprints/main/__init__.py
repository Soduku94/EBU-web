from flask import Blueprint

# Tạo một Blueprint tên là 'main'
main = Blueprint('main', __name__)

# Import routes của blueprint này
from . import routes