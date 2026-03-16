# ToolCrawlTiktok

Tool crawl danh sách user TikTok theo từ khóa, lưu kết quả ra CSV và có giao diện desktop để thao tác nhanh.

## Tính năng

- Tìm user theo từ khóa TikTok (tab Users)
- Tự động lướt danh sách để lấy thêm kết quả
- Chống trùng theo `username`
- Xuất CSV theo format:
  - `Tên;Username;NumOfFollower;NumOfLike`
- GUI có:
  - Nhập từ khóa
  - Auto-generate tên file CSV theo từ khóa (vẫn sửa tay được)
  - Bật/tắt `Headless`
  - Bật/tắt `Tự động lướt`
  - Nút `Chạy crawl` và `Dừng crawl`

## Cấu trúc project

- `crawl.py`: lõi crawl bằng Playwright
- `gui.py`: giao diện Tkinter
- `crawl.ipynb`: notebook thử nghiệm

## Yêu cầu

- Python 3.10+
- Windows (đã test trên Windows)
- Playwright + browser runtime

## Cài đặt

```bash
pip install playwright
python -m playwright install
```

Nếu cần cài channel Chrome riêng:

```bash
python -m playwright install chrome
```

## Chạy ứng dụng GUI

```bash
python gui.py
```

### Giải thích nhanh các tùy chọn

- **Headless**
  - Bật: chạy ẩn, không mở cửa sổ browser
  - Tắt: mở browser để quan sát trực tiếp
- **Tự động lướt**
  - Bật: crawler tự cuộn list user để lấy thêm dữ liệu
  - Tắt: chỉ lấy dữ liệu đang hiển thị
- **Idle rounds**
  - Số vòng liên tiếp không thấy user mới thì dừng
- **Scroll pause (ms)**
  - Thời gian nghỉ giữa các lần lướt

## Chạy bằng script (không GUI)

```bash
python crawl.py
```

Trong file `crawl.py`, bạn có thể chỉnh nhanh:

- `SEARCH_QUERY`
- `OUTPUT_CSV`
- `MAX_IDLE_SCROLL_ROUNDS`
- `SCROLL_PAUSE_MS`

## Output CSV

File CSV dùng dấu `;`, ví dụ:

```csv
Tên;Username;NumOfFollower;NumOfLike
Nhà Đất Hà Nội;thangyuno8389;1520;2060
```

## Lưu ý vận hành

- TikTok có thể thay đổi UI/DOM theo thời điểm, làm giảm số lượng dữ liệu lấy được.
- Khi `Headless` bị hạn chế bởi nền tảng, thử tắt Headless để tăng độ ổn định.
- Nếu thấy số user không tăng, tăng `Idle rounds` và `Scroll pause (ms)`.

## Troubleshooting

### 1) `Import "playwright.async_api" could not be resolved`

Đây thường là cảnh báo của VS Code do sai interpreter, không hẳn lỗi runtime.

- Chọn đúng Python interpreter đã cài Playwright
- Hoặc cài lại trong đúng môi trường:

```bash
pip install playwright
python -m playwright install
```

### 2) Không mở được browser / không crawl được

- Thử chạy lại `python -m playwright install`
- Thử tắt/bật `Headless`
- Đảm bảo mạng truy cập TikTok ổn định

## Gợi ý mở rộng

- Thêm cột `ProfileUrl`
- Lọc kết quả theo từ khóa trong `Tên`/`Username`
- Đóng gói `.exe` bằng PyInstaller
