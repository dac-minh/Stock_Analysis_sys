# Hướng dẫn Từng bước: Xây dựng Luồng Dữ liệu Realtime (WebSocket → Kafka → MinIO)

Chào mừng bạn! Tài liệu này là lộ trình chi tiết để xây dựng hệ thống thu thập dữ liệu chứng khoán realtime, từ lúc nhận tin nhắn từ WebSocket cho đến khi lưu trữ an toàn trong Data Lake (MinIO) và sẵn sàng cho Airflow xử lý.

---

## 📋 Điều kiện tiên quyết (Prerequisites)
Trước khi bắt đầu, hãy đảm bảo bạn có:
- **Docker & Docker Compose:** Để chạy Kafka, Zookeeper và MinIO.
- **Python 3.9+:** Để viết Worker thu thập dữ liệu.
- **Quyền truy cập Airflow:** Để quản lý Variable và Connection.

---

## 🏗️ Giai đoạn 1: Thiết lập Hạ tầng (Infrastructure)

### Bước 1: Khởi tạo MinIO Bucket
Dùng giao diện MinIO Console hoặc CLI để tạo bucket:
- **Bucket Name:** `thongtin-congty-va-bctc`
- **Policy:** Đảm bảo user của bạn có quyền `Read/Write`.

### Bước 2: Cấu hình Airflow Connection
Vào Airflow UI -> Admin -> Connections, tạo mới:
- **Conn Id:** `minio_finance`
- **Conn Type:** `S3`
- **Extra:** `{"endpoint_url": "http://minio:9000", "aws_access_key_id": "admin", "aws_secret_access_key": "12345678"}`

### Bước 3: Chạy Kafka & Tạo Topic
Chạy lệnh sau để tạo "phễu" chứa dữ liệu:
```bash
kafka-topics --create --bootstrap-server localhost:9092 \
  --topic market.quotes.raw \
  --partitions 3 \
  --replication-factor 1 # Dùng 3 trong môi trường Production
```

---

## 🛠️ Giai đoạn 2: Viết Ingestion Worker (WebSocket → Kafka)

Bạn cần một script Python đóng vai trò "người vận chuyển" dữ liệu.

### Bước 1: Cấu hình mã nguồn (Logic cốt lõi)
Worker sẽ làm 3 việc:
1.  **Kết nối** tới `wss://stream2.simplize.vn/ws`.
2.  **Gửi lệnh `sub`** cho danh sách mã chứng khoán.
3.  **Đẩy message** nhận được vào Kafka topic `market.quotes.raw`.

### Bước 2: Lưu ý về độ tin cậy
- **Ping/Pong:** Phải phản hồi tin nhắn `{"event":"ping"}` để không bị ngắt kết nối.
- **Auto-reconnect:** Sử dụng vòng lặp `while True` với `try/except` để tự động kết nối lại khi rớt mạng.

---

## 📥 Giai đoạn 3: Đẩy dữ liệu vào MinIO (Kafka → MinIO Sink)

Đây là bước quan quan trọng để lưu trữ dữ liệu vĩnh viễn.

### Phương án: Sử dụng Kafka Connect S3 Sink
Cấu hình này sẽ tự động "hốt" dữ liệu từ Kafka và đóng gói thành file Parquet đẩy lên MinIO mỗi 5 phút.

**File cấu hình `minio-sink.json`:**
```json
{
  "name": "minio-sink-connector",
  "config": {
    "connector.class": "io.confluent.connect.s3.S3SinkConnector",
    "topics": "market.quotes.raw",
    "s3.bucket.name": "thongtin-congty-va-bctc",
    "s3.region": "us-east-1",
    "s3.endpoint.url": "http://minio:9000",
    "storage.class": "io.confluent.connect.s3.storage.S3Storage",
    "format.class": "io.confluent.connect.s3.format.parquet.ParquetFormat",
    "flush.size": "1000", 
    "rotate.interval.ms": "300000",
    "path.format": "'realtime'/YYYY/MM/dd/HH"
  }
}
```

---

## 🔄 Giai đoạn 4: Tích hợp Airflow & Xử lý hậu kỳ

Dữ liệu bây giờ đã nằm yên trong MinIO dưới dạng file Parquet. Giờ là lúc Airflow vào cuộc.

### Bước 1: Tạo Sensor theo dõi dữ liệu
Trong DAG của bạn, dùng `S3KeySensor` để đợi file xuất hiện:
```python
wait_for_data = S3KeySensor(
    task_id='wait_for_realtime_data',
    bucket_name='thongtin-congty-va-bctc',
    bucket_key='realtime/{{ ds_nodash }}/*',
    aws_conn_id='minio_finance'
)
```

### Bước 2: ETL vào Database
Viết một task Python để:
1.  Đọc file Parquet từ `thongtin-congty-va-bctc`.
2.  Transform dữ liệu theo chuẩn.
3.  Lưu vào Postgres schema `hethong_phantich_chungkhoan`.

---

## 🛡️ Giai đoạn 5: Kiểm tra & Vận hành (Validation)

Người mới cần kiểm tra 3 điểm "chết" sau:
1.  **Check WebSocket:** Worker có nhận được dữ liệu không? (Xem log của Worker).
2.  **Check Kafka Lag:** Kafka có bị ùn ứ không? (Dùng `kafka-consumer-groups`).
3.  **Check MinIO:** File Parquet có được tạo ra trong bucket không? (Dùng MinIO Browser).

---

## 💡 Mẹo nhỏ cho người mới
- **Bắt đầu nhỏ:** Thử subscribe 1-2 mã chứng khoán (ví dụ: `FPT`, `VIC`) trước khi chạy toàn bộ thị trường.
- **Log là bạn:** Ghi log chi tiết cho mỗi message nhận được ở giai đoạn phát triển.
- **Format Parquet:** Luôn dùng Parquet thay vì JSON để tiết kiệm 80% dung lượng lưu trữ trên MinIO.

---
*Người soạn: Gemini CLI Agent*
*Cập nhật lần cuối: 2026-05-05*
