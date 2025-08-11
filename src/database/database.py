import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# Enable SQLAlchemy logging
logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Lấy chuỗi kết nối từ biến môi trường
DB_URI = os.getenv("DATABASE_CONNECTION")

# Khởi tạo engine và sessionmaker cho ORM
engine = create_engine(DB_URI, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import Base từ models (chỉ import 1 nơi duy nhất)

# Import Base dùng chung cho ORM
from src.models.base import Base



def get_db():
    """
    Dùng cho FastAPI dependency injection (DI):
    - Khi dùng trong route hoặc service FastAPI, khai báo: db: Session = Depends(get_db)
    - Hàm này là generator, trả về session qua yield, FastAPI sẽ tự động quản lý đóng/mở session.
    - KHÔNG dùng hàm này cho các script, tool, hoặc code ngoài FastAPI DI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """
    Dùng cho các script, tool, hoặc code ngoài FastAPI:
    - Trả về một SQLAlchemy Session (SessionLocal())
    - Bạn phải tự quản lý vòng đời session: nhớ gọi session.close() hoặc dùng with context nếu cần.
    - KHÔNG dùng hàm này cho FastAPI dependency injection.
    """
    return SessionLocal()
