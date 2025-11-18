from threading import Thread
from flask import current_app, render_template
from flask_mail import Message
from .extensions import mail


def send_async_email(app, msg):
    """Hàm chạy email trong 1 thread riêng."""
    with app.app_context():
        mail.send(msg)


def send_order_confirmation_email(order):
    """
    Soạn và gửi email xác nhận đơn hàng.
    'order' là đối tượng Order đã được commit.
    """
    app = current_app._get_current_object()

    # Tạo đối tượng Message
    msg = Message(
        subject=f'Xác nhận đơn hàng #{order.id} - Home Fit Pro',
        sender=('Home Fit Pro', app.config['MAIL_USERNAME']),
        recipients=[order.customer_email]
    )

    # Render template HTML cho nội dung email
    # Chúng ta gửi cả 2 phiên bản:
    # - HTML: Cho các trình duyệt mail hiện đại
    # - Text: Cho các trình duyệt mail cũ hoặc chế độ an toàn
    msg.body = render_template('email/order_confirmation.txt', order=order)
    msg.html = render_template('email/order_confirmation.html', order=order)

    # Gửi email bằng 1 thread riêng (để không làm "đơ" trang web)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr