from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, RadioField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Email, Length, InputRequired, EqualTo, Optional
from wtforms import RadioField

class CheckoutForm(FlaskForm):
    """Form điền thông tin khi thanh toán."""
    full_name = StringField('Họ và Tên', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Số điện thoại', validators=[DataRequired(), Length(min=9, max=11)])
    # địa chỉ mới
    province = StringField('Tỉnh / Thành phố', validators=[DataRequired()])
    district = StringField('Quận / Huyện', validators=[DataRequired()])
    ward = StringField('Phường / Xã', validators=[DataRequired()])
    specific_address = StringField('Địa chỉ chi tiết (Số nhà, đường...)',validators=[Optional()])
    # mã giảm giá
    coupon_code = StringField('Mã giảm giá (Nếu có)')
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


class ParqForm(FlaskForm):
    """Bảng câu hỏi PAR-Q (7 câu)."""
    # Choices: 'yes' -> True, 'no' -> False
    choices = [('no', 'Không'), ('yes', 'Có')]

    q1 = RadioField('1. Bác sĩ có từng nói bạn bị bệnh tim và chỉ nên tập thể dục khi có sự giám sát?',
                    choices=choices, validators=[DataRequired()])

    q2 = RadioField('2. Bạn có cảm thấy đau ngực khi tham gia hoạt động thể chất không?',
                    choices=choices, validators=[DataRequired()])

    q3 = RadioField('3. Trong tháng qua, bạn có bị đau ngực khi KHÔNG tham gia hoạt động thể chất không?',
                    choices=choices, validators=[DataRequired()])

    q4 = RadioField('4. Bạn có bị mất thăng bằng do chóng mặt hoặc từng bị mất ý thức không?',
                    choices=choices, validators=[DataRequired()])

    q5 = RadioField(
        '5. Bạn có vấn đề về xương khớp (lưng, đầu gối...) có thể tồi tệ hơn nếu thay đổi cường độ vận động?',
        choices=choices, validators=[DataRequired()])

    q6 = RadioField('6. Bạn có đang kê đơn thuốc cho huyết áp hoặc bệnh tim không?',
                    choices=choices, validators=[DataRequired()])

    q7 = RadioField('7. Bạn có biết lý do nào khác khiến bạn không nên tham gia hoạt động thể chất không?',
                    choices=choices, validators=[DataRequired()])

    submit = SubmitField('Gửi đánh giá')


# Import SelectField
from wtforms import SelectField


class NeedsAssessmentForm(FlaskForm):
    """Form đánh giá nhu cầu tập luyện."""

    goal = SelectField('1. Mục tiêu chính của bạn là gì?', choices=[
        ('lose_weight', 'Giảm cân / Đốt mỡ'),
        ('gain_muscle', 'Tăng cơ bắp / Sức mạnh'),
        ('health', 'Duy trì sức khỏe / Tim mạch'),
        ('recovery', 'Phục hồi / Thư giãn (Yoga)')
    ], validators=[DataRequired()])

    experience = SelectField('2. Kinh nghiệm tập luyện của bạn?', choices=[
        ('newbie', 'Mới bắt đầu (Chưa bao giờ tập)'),
        ('intermediate', 'Đã từng tập (Biết cơ bản)'),
        ('pro', 'Tập thường xuyên (Nâng cao)')
    ], validators=[DataRequired()])

    space = SelectField('3. Không gian tập tại nhà?', choices=[
        ('small', 'Nhỏ / Hẹp (Căn hộ, Phòng ngủ)'),
        ('medium', 'Trung bình (Phòng khách rộng)'),
        ('large', 'Rộng (Có phòng tập riêng / Sân vườn)')
    ], validators=[DataRequired()])

    budget = SelectField('4. Ngân sách dự kiến?', choices=[
        ('low', 'Dưới 1 triệu'),
        ('medium', 'Từ 1 - 5 triệu'),
        ('high', 'Trên 5 triệu'),
        ('unlimited', 'Thoải mái, miễn là tốt')
    ], validators=[DataRequired()])

    submit = SubmitField('Xem Gợi ý Phù hợp')