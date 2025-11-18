import hashlib
import hmac
import urllib.parse
from datetime import datetime
from flask import current_app, request


def get_vnpay_payment_url(order_id, total_price, order_desc, ip_addr):
    """
    Xây dựng URL để chuyển hướng người dùng sang VNPay.
    """
    config = current_app.config

    # Dữ liệu bắt buộc
    vnp_Params = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': config['VNPAY_TMN_CODE'],
        'vnp_Amount': str(int(total_price * 100)),  # VNPay yêu cầu nhân 100 (đơn vị xu)
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': str(order_id),  # Mã đơn hàng của bạn
        'vnp_OrderInfo': order_desc,  # Mô tả đơn hàng
        'vnp_OrderType': 'other',
        'vnp_Locale': 'vn',
        'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
        'vnp_IpAddr': ip_addr,
        'vnp_ReturnUrl': config['VNPAY_RETURN_URL'],
        'vnp_BankCode': 'NCB'  # Có thể để trống, hoặc 'NCB' để test
    }

    # Sắp xếp các tham số theo thứ tự alphabet
    input_data = sorted(vnp_Params.items())

    # Tạo chuỗi query
    query_string = urllib.parse.urlencode(input_data, doseq=True)

    # Tạo chữ ký (hash)
    secret_key = config['VNPAY_HASH_SECRET'].encode('utf-8')
    hmac_hash = hmac.new(secret_key, query_string.encode('utf-8'), hashlib.sha512)
    vnp_SecureHash = hmac_hash.hexdigest()

    # Nối chữ ký vào URL
    query_string += '&vnp_SecureHash=' + vnp_SecureHash

    payment_url = config['VNPAY_PAYMENT_URL'] + '?' + query_string
    return payment_url


def validate_vnpay_response(vnp_response_data):
    """
    Xác thực phản hồi (Return hoặc IPN) từ VNPay.
    vnp_response_data là request.args (hoặc request.form)
    """
    config = current_app.config
    secret_key = config['VNPAY_HASH_SECRET'].encode('utf-8')

    # Lấy vnp_SecureHash từ phản hồi
    vnp_SecureHash_received = vnp_response_data.get('vnp_SecureHash')

    # Xây dựng lại chuỗi query và hash
    input_data = {}
    for key, value in vnp_response_data.items():
        if key != 'vnp_SecureHash':
            input_data[key] = value

    input_data_sorted = sorted(input_data.items())
    query_string = urllib.parse.urlencode(input_data_sorted, doseq=True)

    hmac_hash = hmac.new(secret_key, query_string.encode('utf-8'), hashlib.sha512)
    vnp_SecureHash_calculated = hmac_hash.hexdigest()

    # So sánh 2 chữ ký
    return vnp_SecureHash_calculated == vnp_SecureHash_received