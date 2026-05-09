import sys
import asyncio
from pathlib import Path

# Thêm đường dẫn BE vào sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database.database import AsyncSessionLocal, engine


async def test_database_connection():
    """Kiểm tra kết nối database (Async)"""
    try:
        # Với AsyncEngine, phải dùng 'async with'
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("✓ Kết nối database thành công!")
            # fetchone() cũng cần được xử lý từ kết quả đã await
            print(f"  Test query result: {result.fetchone()}")
            return True
    except Exception as e:
        print(f"✗ Lỗi kết nối database: {str(e)}")
        return False


async def test_custom_query():
    """Kiểm tra thực thi một câu truy vấn nghiệp vụ thực tế (Async)"""
    async with AsyncSessionLocal() as db:
        try:
            # Giải pháp 1: Set search_path trước khi chạy query
            await db.execute(text("SET search_path TO hethong_phantich_chungkhoan, public"))

            query = text("""
                SELECT
                    cur.trading_date,
                    t.ticker,
                    cur.close AS value,
                    cur.close - prev.close AS change,
                    CASE WHEN prev.close > 0
                        THEN ROUND(((cur.close - prev.close) / prev.close * 100)::numeric, 2)
                        ELSE 0 END AS percent
                FROM (VALUES
                    ('VNINDEX', 1),
                    ('VN30', 2),
                    ('HNXINDEX', 3),
                    ('UPCOMINDEX', 4)
                ) AS t(ticker, sort_order)
                CROSS JOIN LATERAL (
                    SELECT close, trading_date
                    FROM market_index  -- Bây giờ nó sẽ tìm trong schema đã set ở trên
                    WHERE ticker = t.ticker
                    ORDER BY trading_date DESC
                    LIMIT 1
                ) cur
                CROSS JOIN LATERAL (
                    SELECT close
                    FROM market_index
                    WHERE ticker = t.ticker
                    ORDER BY trading_date DESC
                    OFFSET 1 LIMIT 1
                ) prev
                ORDER BY t.sort_order;
            """)

            print("  Đang chạy truy vấn nghiệp vụ...")
            result = await db.execute(query)
            rows = result.fetchall()
            # ... phần xử lý in kết quả giữ nguyên ...

            if rows:
                print(f"✓ Truy vấn thành công! Lấy được {len(rows)} dòng dữ liệu:")
                for row in rows:
                    # Truy cập row theo index hoặc tên cột
                    print(f"  - Ticker: {row[1]}, Giá: {row[2]}, Thay đổi: {row[3]}, %: {row[4]}%")
            else:
                print("⚠ Truy vấn chạy thành công nhưng bảng market_index chưa có dữ liệu.")

            return True
        except Exception as e:
            print(f"✗ Lỗi thực thi truy vấn: {str(e)}")
            return False


async def main():
    print("=" * 60)
    print("KIỂM TRA TRUY VẤN DỮ LIỆU (ASYNC MODE)")
    print("=" * 60)

    print("\n1. Kiểm tra kết nối engine...")
    await test_database_connection()

    print("\n2. Kiểm tra truy vấn lấy dữ liệu thị trường...")
    await test_custom_query()

    print("\n" + "=" * 60)
    # Luôn đóng engine khi kết thúc script test
    await engine.dispose()


if __name__ == "__main__":
    # Khởi chạy loop cho code async
    asyncio.run(main())