# Chẩn đoán dữ liệu trước thử nghiệm V3

Nguồn: `artifacts/binary_improvement_v3/diagnostic_v2_20261021.json`, tính từ
dự đoán V2 đã có. Đây là phân tích lịch sử sau khi đã xem dữ liệu, không phải
bằng chứng trên tập kiểm thử mới. Các ngưỡng tối ưu trực tiếp trên quý IV dưới
đây chỉ dùng chẩn đoán; không được đưa vào model hay dùng chọn cấu hình V3.

## Những gì số liệu cho thấy

Quần thể quý IV/2022 gồm 79.087 chuyến Arrival và 79.020 chuyến Departure.
Không có giá trị thiếu ở các cột đặc trưng đã chuẩn bị cho hai quần thể này.
Vì vậy, số liệu hiện tại không ủng hộ giải thích rằng chỉ số thấp chủ yếu do
thiếu dữ liệu ở đầu vào đã chuẩn bị.

| Bài toán | Tỷ lệ trễ quý III | Tỷ lệ trễ quý IV | F1 baseline V2 | F1 tốt nhất V2 tại ngưỡng đã khóa | F1 tối đa khi nhìn trước nhãn quý IV | Mốc F1 phải đạt |
|---|---:|---:|---:|---:|---:|---:|
| Arrival | 16,8012% | 15,0138% | 0,330305 | 0,339797 | 0,347841 | 0,350305 |
| Departure | 20,6434% | 17,7841% | 0,359557 | 0,371444 | 0,377323 | 0,379557 |

Ở cả hai bài toán, ngay cả ngưỡng chọn trực tiếp từ nhãn quý IV của các model
V2 đã thử cũng chưa đủ vượt mốc F1. Do đó, chỉ sửa ngưỡng của các model này
không thể đáp ứng yêu cầu hiện tại; cần cải thiện khả năng phân biệt và xếp
hạng chuyến có nguy cơ trễ. Bảng này không chứng minh các model khác không thể
đạt mốc.

Tỷ lệ trễ thay đổi giữa giai đoạn chọn ngưỡng và giai đoạn chấm điểm. Đây là
một dạng dịch chuyển phân phối quan sát được; tác động riêng của nó lên F1
chưa được tách bằng thực nghiệm nhân quả. V3 kiểm tra hai lịch cập nhật dữ liệu
A/B, calibration theo thời gian và ngưỡng được chọn trước quý IV để đánh giá
những phương án khắc phục cụ thể.

Các lỗi bỏ sót cũng tập trung theo nhóm và ngày. Trong baseline V2, 10 ngày có
nhiều lỗi bỏ sót nhất chiếm 23,03% tổng FN Arrival và 18,84% FN Departure.
Ngày 23/12 có 443/785 chuyến Arrival trễ, trong đó bỏ sót 260 chuyến. Các con số
này cho thấy rủi ro biến động theo ngày; chúng không đủ để kết luận nguyên nhân
là thời tiết, vận hành hay một sự kiện cụ thể. V3 chỉ thêm thông tin lịch biết
trước và thống kê từ quá khứ, không dùng nhãn hay thông tin thực tế của ngày
đang dự đoán.

## Cách V3 kiểm tra các giả thuyết

- Đối chứng huấn luyện lại cùng cấu hình giúp phân biệt lợi ích cập nhật dữ
  liệu với lợi ích HPO. Đối chứng cũng phải vượt đầy đủ cùng các mốc nghiệm thu.
- Đối chứng đặc trưng cùng dòng và cùng siêu tham số so sánh mã hóa ban đầu,
  danh mục tự nhiên và thống kê lịch sử. Thống kê nhãn khi huấn luyện chỉ dùng
  các tháng trước; lúc suy luận giữ nguyên bản đồ đã học.
- Cửa sổ hai/ba năm và trọng số thời gian kiểm tra ảnh hưởng của lịch sử xa.
- Chuyên gia DL và calibration theo hãng được kiểm tra trên các fold trước
  quý IV. Hãng ít dữ liệu hoặc chưa từng thấy dùng nhánh toàn cục.
- Quý IV/2020 chỉ dùng kiểm tra sức chịu đựng. Quý IV/2022 được chấm sau khi
  khóa model/ngưỡng; năm 2023 chỉ đối chiếu sau khi khóa quyết định quý IV.

Kết luận model nào cải thiện và có đạt đủ yêu cầu hay không phải dựa vào
`RESULTS.vi.md`, `model_results.json` và `validation.json` của lượt chạy đầy đủ.
Không được suy ra kết quả nghiệm thu từ riêng những số liệu chẩn đoán này.
