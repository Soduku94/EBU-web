from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    """Form cho trang Đăng nhập."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    remember_me = BooleanField('Ghi nhớ đăng nhập')
    submit = SubmitField('Đăng nhập')

class RegistrationForm(FlaskForm):
    """Form cho trang Đăng ký."""
    username = StringField('Tên đăng nhập', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    password2 = PasswordField(
        'Nhập lại mật khẩu', validators=[DataRequired(), EqualTo('password', message='Mật khẩu phải trùng khớp.')])
    submit = SubmitField('Đăng ký')

    # Hàm validate_... tự động được WTForms gọi
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Tên đăng nhập này đã được sử dụng.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email này đã được sử dụng.')