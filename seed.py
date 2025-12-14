import random
from faker import Faker
from app import create_app, db
from app.models import User, Role, Category, Product, Review, Post, ProductImage
from werkzeug.security import generate_password_hash

# Cấu hình Faker tiếng Việt
fake = Faker('vi_VN')

app = create_app()


def seed_database():
    with app.app_context():
        print("🗑️  Đang xóa dữ liệu cũ...")
        db.drop_all()  # Xóa toàn bộ bảng
        db.create_all()  # Tạo lại bảng mới tinh

        print("🌱 Đang tạo Roles (Vai trò)...")
        admin_role = Role(name='Admin')
        user_role = Role(name='User')
        db.session.add_all([admin_role, user_role])
        db.session.commit()

        print("👤 Đang tạo Admin & User mẫu...")
        # 1. Tạo Admin xịn (Để bạn đăng nhập)
        admin = User(
            username='Admin',
            email='admin@gmail.com',
            password_hash=generate_password_hash('123456'),  # Mật khẩu là 123456
            full_name='Quản Trị Viên',
            role=admin_role,

        )

        # 2. Tạo User mẫu
        users = []
        for _ in range(10):
            user = User(
                # Sửa: Thêm .unique để đảm bảo không trùng
                username=fake.unique.user_name(),
                email=fake.unique.email(),

                password_hash=generate_password_hash('123456'),
                full_name=fake.name(),
                phone=fake.phone_number(),
                address=fake.address(),
                role=user_role
            )
            users.append(user)

        db.session.add(admin)
        db.session.add_all(users)
        db.session.commit()

        print("📦 Đang tạo Danh mục & Sản phẩm...")
        # 3. Tạo Danh mục
        cats = [
            Category(name='Máy chạy bộ'),
            Category(name='Xe đạp tập'),
            Category(name='Giàn tạ đa năng'),
            Category(name='Dụng cụ Yoga'),
            Category(name='Phụ kiện Gym')
        ]
        db.session.add_all(cats)
        db.session.commit()

        # 4. Tạo Sản phẩm "Đẹp" (Dữ liệu cứng để nhìn cho chuẩn)
        # Lưu ý: Bạn cần đảm bảo có file ảnh tương ứng trong static/images/products/
        # Hoặc dùng link online tạm thời

        product_list = [
            {
                "name": "Máy chạy bộ đa năng HomeFit X1",
                "price": 8500000,
                "cat": cats[0],  # Máy chạy bộ
                "img": "https://img.freepik.com/free-photo/gym-with-modern-equipment_1262-16782.jpg",  # Link ảnh demo
                "desc": "Máy chạy bộ điện đa năng, động cơ 3.0HP mạnh mẽ, phù hợp cho gia đình."
            },
            {
                "name": "Xe đạp tập thể dục AirBike",
                "price": 2500000,
                "cat": cats[1],  # Xe đạp
                "img": "https://img.freepik.com/free-photo/woman-training-gym-exercise-bike_144627-28564.jpg",
                "desc": "Xe đạp tập toàn thân, giúp săn chắc cơ đùi và cải thiện tim mạch."
            },
            {
                "name": "Giàn tạ đa năng KingSport",
                "price": 12000000,
                "cat": cats[2],  # Giàn tạ
                "img": "https://img.freepik.com/free-photo/modern-gym-interior-with-equipment_23-2148037989.jpg",
                "desc": "Hỗ trợ hơn 15 bài tập cơ bắp: Đẩy ngực, kéo xô, đá chân..."
            },
            {
                "name": "Thảm Yoga định tuyến PU",
                "price": 450000,
                "cat": cats[3],  # Yoga
                "img": "https://img.freepik.com/free-photo/rolled-yoga-mats-floor_23-2147826315.jpg",
                "desc": "Thảm cao su non bám dính cực tốt, có vạch định tuyến giúp tập chuẩn form."
            },
            {
                "name": "Bộ tạ tay điều chỉnh 24kg",
                "price": 1800000,
                "cat": cats[4],  # Phụ kiện
                "img": "https://img.freepik.com/free-photo/dumbbells-floor-gym-ai-generative_123827-23744.jpg",
                "desc": "Tạ tay thông minh, thay đổi trọng lượng chỉ bằng 1 cú xoay."
            },
            # Thêm các sản phẩm giả lập khác để lấp đầy trang
        ]

        # Tạo thêm 15 sản phẩm ngẫu nhiên để test phân trang
        for i in range(15):
            p_cat = random.choice(cats)
            product_list.append({
                "name": f"{p_cat.name} Pro Series {i + 1}",
                "price": random.randint(5, 50) * 100000,
                "cat": p_cat,
                "img": "https://via.placeholder.com/800x800.png?text=Home+Fit+Pro",  # Ảnh giữ chỗ
                "desc": fake.paragraph(nb_sentences=5)
            })

        db_products = []
        for p_data in product_list:
            from slugify import slugify
            import uuid
            slug = f"{slugify(p_data['name'])}-{uuid.uuid4().hex[:4]}"

            prod = Product(
                name=p_data['name'],
                slug=slug,
                description=p_data['desc'],
                price=p_data['price'],
                stock=random.randint(5, 50),
                category=p_data['cat'],
                image_url=p_data['img'],
                is_active=True
            )
            db_products.append(prod)

        db.session.add_all(db_products)
        db.session.commit()

        print("⭐ Đang tạo Đánh giá (Reviews) giả...")
        # Mỗi sản phẩm có ngẫu nhiên 0-5 đánh giá từ user ảo
        for prod in db_products:
            num_reviews = random.randint(0, 5)
            for _ in range(num_reviews):
                reviewer = random.choice(users)  # Chọn bừa 1 user
                review = Review(
                    rating=random.randint(3, 5),  # Đánh giá 3-5 sao
                    comment=fake.sentence(nb_words=10),
                    author=reviewer,
                    product=prod
                )
                db.session.add(review)

        db.session.commit()

        print("✅ HOÀN TẤT! Database đã được làm mới.")
        print("👉 Tài khoản Admin: admin@gmail.com / 123456")


if __name__ == '__main__':
    seed_database()