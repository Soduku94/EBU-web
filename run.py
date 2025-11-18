from app import create_app, db
from app.models import User, Role, Product, Category, Order, Post, Review # Import tất cả models
import os

config_name = os.getenv('FLASK_CONFIG') or 'default'
app = create_app(config_name)

@app.shell_context_processor
def make_shell_context():
    """
    Tự động import các đối tượng này khi chạy 'flask shell'
    """
    return dict(db=db, User=User, Role=Role, Product=Product,
                Category=Category, Order=Order, Post=Post, Review=Review)

if __name__ == '__main__':
    app.run()