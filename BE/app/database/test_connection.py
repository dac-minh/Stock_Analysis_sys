import sys
import asyncio
from pathlib import Path
from sqlalchemy import text

# 1. Đảm bảo Python tìm thấy thư mục 'app'
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 2. Import đúng tên AsyncSessionLocal từ database.py
from app.database.database import AsyncSessionLocal, engine
from app.core.config import get_settings

TARGET_SCHEMA = "hethong_phantich_chungkhoan"


async def test_database_connection():
    """Kiểm tra kết nối engine (Async)"""
    print("\n1. Kiểm tra kết nối engine...")
    try:
        # Với AsyncEngine, phải dùng 'async with'
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("✓ Kết nối database thành công!")

            db_info_query = text(
                "SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version()"
            )
            result = await connection.execute(db_info_query)
            db_info = result.fetchone()
            print(f"  Database : {db_info[0]}")
            print(f"  User     : {db_info[1]}")
            print(f"  Host:Port: {db_info[2]}:{db_info[3]}")
            return True
    except Exception as e:
        print(f"✗ Lỗi kết nối database: {str(e)}")
        return False


async def test_session_and_schema():
    """Kiểm tra Session và Schema (Async)"""
    print("\n2. Kiểm tra Session và Schema...")
    try:
        # Sử dụng AsyncSessionLocal đã định nghĩa trong database.py
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            print("✓ AsyncSessionLocal tạo thành công!")

            # Kiểm tra schema tồn tại
            query = text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema")
            result = await db.execute(query, {"schema": TARGET_SCHEMA})
            if result.fetchone():
                print(f"✓ Schema '{TARGET_SCHEMA}' tồn tại!")
                return True
            else:
                print(f"✗ Schema '{TARGET_SCHEMA}' KHÔNG tồn tại!")
                return False
    except Exception as e:
        print(f"✗ Lỗi thao tác Session: {str(e)}")
        return False


async def run_all_tests():
    """Hàm chạy chính"""
    settings = get_settings()
    print("=" * 60)
    print("TEST KẾT NỐI DATABASE - ASYNC MODE")
    print(f"URL: {settings.DATABASE_URL.split('@')[-1]}")  # Ẩn password khi in
    print("=" * 60)

    conn_ok = await test_database_connection()
    if conn_ok:
        await test_session_and_schema()

    print("\n" + "=" * 60)
    print("HOÀN TẤT KIỂM TRA")
    print("=" * 60)

    # Đóng mọi kết nối còn lại trong pool
    await engine.dispose()


if __name__ == "__main__":
    # Vì là code async, chúng ta phải khởi chạy qua asyncio
    asyncio.run(run_all_tests())