from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    remember = BooleanField('Ghi nhớ đăng nhập')
    submit = SubmitField('Đăng nhập')

class RegistrationForm(FlaskForm):
    full_name = StringField('Họ và tên', validators=[DataRequired(), Length(min=2, max=50)])

    email = StringField('Email', validators=[DataRequired(), Email()])

    password = PasswordField('Mật khẩu', validators=[DataRequired(), Length(min=6)])

    confirm_password = PasswordField('Nhập lại mật khẩu', validators=[
        DataRequired(),
        EqualTo('password', message='Mật khẩu không khớp.')
    ])

    submit = SubmitField('Đăng ký')

    # Chỉ cần kiểm tra trùng Email
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email này đã được đăng ký. Vui lòng sử dụng email khác hoặc đăng nhập.')

class ResetPasswordRequestForm(FlaskForm):
    """Form nhập email để yêu cầu reset."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Gửi yêu cầu đặt lại mật khẩu')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Không tìm thấy tài khoản với email này. Vui lòng đăng ký.')

class ResetPasswordForm(FlaskForm):
    """Form nhập mật khẩu mới."""
    password = PasswordField('Mật khẩu mới', validators=[DataRequired()])
    password2 = PasswordField('Nhập lại mật khẩu', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Đặt lại mật khẩu')
