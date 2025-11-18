from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, FloatField, IntegerField
from wtforms.validators import DataRequired, ValidationError, NumberRange
from app.models import Category, Product
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_ckeditor import CKEditorField


# === SỬA LỖI: Đặt hàm này ở đây, bên ngoài tất cả các lớp ===
def category_query():
    """Hàm này trả về danh sách các Category cho QuerySelectField."""
    return Category.query


# =========================================================

class CategoryForm(FlaskForm):
    """Form để thêm/sửa danh mục."""
    name = StringField('Tên Danh mục', validators=[DataRequired()])
    submit = SubmitField('Lưu')

    def validate_name(self, name):
        # Kiểm tra xem tên danh mục đã tồn tại chưa
        category = Category.query.filter_by(name=name.data).first()
        if category:
            raise ValidationError('Tên danh mục này đã tồn tại.')

    # <-- (Không còn hàm category_query ở đây nữa)


class ProductForm(FlaskForm):
    """Form để thêm/sửa sản phẩm."""
    name = StringField('Tên Sản phẩm', validators=[DataRequired()])
    description = TextAreaField('Mô tả')
    price = FloatField('Giá', validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField('Số lượng tồn kho', validators=[DataRequired(), NumberRange(min=0)])
    image_url = StringField('Link hình ảnh (URL)')  # Sẽ cải tiến sau

    # Ô dropdown chọn danh mục
    category = QuerySelectField('Danh mục',
                                query_factory=category_query,  # <-- Bây giờ nó sẽ tìm thấy hàm
                                get_label='name',
                                allow_blank=False,
                                validators=[DataRequired()])

    submit = SubmitField('Lưu Sản phẩm')


# === THÊM CLASS MỚI VÀO CUỐI FILE ===
class PostForm(FlaskForm):
    """Form để Admin viết bài Blog."""
    title = StringField('Tiêu đề bài viết', validators=[DataRequired()])
    # Đây chính là trình soạn thảo "Word thu nhỏ"
    body = CKEditorField('Nội dung', validators=[DataRequired()])
    submit = SubmitField('Đăng bài')