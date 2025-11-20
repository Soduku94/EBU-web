from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, RadioField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Email, Length, InputRequired, EqualTo


class CheckoutForm(FlaskForm):
    """Form điền thông tin khi thanh toán."""
    full_name = StringField('Họ và Tên', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Số điện thoại', validators=[DataRequired(), Length(min=9, max=11)])
    shipping_address = TextAreaField('Địa chỉ nhận hàng', validators=[DataRequired()])

    payment_method = RadioField(
        'Phương thức thanh toán',
        choices=[
            ('COD', 'Thanh toán khi nhận hàng (COD)'),
            ('VNPAY', 'Thanh toán qua VNPay (Sắp có)')  # Tạm thời vô hiệu hóa
        ],
        default='COD',
        validators=[DataRequired()]
    )
    submit = SubmitField('Hoàn tất Đơn hàng')



        # === THÊM CLASS MỚI VÀO ĐÂY (Ở CUỐI FILE) ===
class ReviewForm(FlaskForm):
            """Form để viết đánh giá."""
            rating = RadioField(
                'Đánh giá của bạn',
                choices=[
                    (5, '★★★★★ (Tuyệt vời)'),
                    (4, '★★★★☆ (Tốt)'),
                    (3, '★★★☆☆ (Bình thường)'),
                    (2, '★★☆☆☆ (Tệ)'),
                    (1, '★☆☆☆☆ (Rất tệ)')
                ],
                validators=[InputRequired(message="Bạn vui lòng chọn số sao.")],
                coerce=int  # Chuyển giá trị choice sang kiểu Integer
            )
            comment = TextAreaField('Bình luận của bạn', validators=[DataRequired()])
            submit = SubmitField('Gửi đánh giá')

            class TrackOrderForm(FlaskForm):
                """Form để khách tra cứu đơn hàng."""
                order_id = IntegerField('Mã Đơn hàng (ID)',
                                        validators=[DataRequired(message="Vui lòng nhập mã đơn hàng (chỉ nhập số).")])

                email = StringField('Email',
                                    validators=[DataRequired(message="Vui lòng nhập email bạn đã dùng đặt hàng."),
                                                Email()])

                submit = SubmitField('Tra cứu')


class TrackOrderForm(FlaskForm):
    """Form để khách tra cứu đơn hàng."""
    order_id = IntegerField('Mã Đơn hàng (ID)',
                            validators=[DataRequired(message="Vui lòng nhập mã đơn hàng (chỉ nhập số).")])

    email = StringField('Email',
                        validators=[DataRequired(message="Vui lòng nhập email bạn đã dùng đặt hàng."), Email()])

    submit = SubmitField('Tra cứu')


class ContactForm(FlaskForm):
    """Form cho trang Liên hệ."""
    name = StringField('Tên của bạn', validators=[DataRequired(message="Vui lòng nhập tên.")])
    email = StringField('Email', validators=[DataRequired(message="Vui lòng nhập email."), Email(message="Email không hợp lệ.")])
    subject = StringField('Chủ đề', validators=[DataRequired(message="Vui lòng nhập chủ đề.")])
    message = TextAreaField('Nội dung tin nhắn', validators=[DataRequired(message="Vui lòng nhập nội dung.")])
    submit = SubmitField('Gửi tin nhắn')

class UpdateProfileForm(FlaskForm):
        """Form cập nhật thông tin cá nhân."""
        full_name = StringField('Họ và Tên', validators=[DataRequired()])
        email = StringField('Email', validators=[DataRequired(), Email()],
                            render_kw={'readonly': True})  # Email thường không cho đổi để tránh rắc rối
        phone = StringField('Số điện thoại', validators=[DataRequired(), Length(min=9, max=11)])
        address = TextAreaField('Địa chỉ mặc định', validators=[DataRequired()])
        submit_profile = SubmitField('Cập nhật Thông tin')

class ChangePasswordForm(FlaskForm):
        """Form đổi mật khẩu (yêu cầu mật khẩu cũ)."""
        old_password = PasswordField('Mật khẩu hiện tại', validators=[DataRequired()])
        new_password = PasswordField('Mật khẩu mới', validators=[DataRequired(), Length(min=6,
                                                                                        message="Mật khẩu phải dài hơn 6 ký tự.")])
        confirm_password = PasswordField('Nhập lại mật khẩu mới', validators=[DataRequired(), EqualTo('new_password',
                                                                                                      message='Mật khẩu mới không khớp.')])
        submit_password = SubmitField('Đổi Mật khẩu')

