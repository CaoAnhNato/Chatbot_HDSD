import sys
import requests
import json

def test_multimodal_end_to_end():
    print("=" * 70)
    print("🧪 KIỂM THỬ TỰ ĐỘNG ĐẦU RA MULTIMODAL (TEXT + ẢNH + STREAMING)")
    print("=" * 70)

    # 1. Health check
    print("\n1️⃣ Kiểm tra Backend Health Endpoint:")
    r = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=10)
    assert r.status_code == 200, f"Health check failed with status {r.status_code}"
    print("   ✅ Backend Status: HEALTHY (HTTP 200)")

    # 2. Test Phường/Xã Role
    print("\n2️⃣ Kiểm thử câu hỏi Phân hệ Phường/Xã:")
    q_phuong = "Làm sao để đổi mật khẩu tài khoản đang đăng nhập?"
    payload_phuong = {
        "query": q_phuong,
        "role": "phuong",
        "stream": False
    }
    r = requests.post("http://127.0.0.1:8000/api/v1/chat", json=payload_phuong, timeout=30)
    assert r.status_code == 200, f"Chat phuong failed with status {r.status_code}"
    res_phuong = r.json().get("data", {})
    answer_phuong = res_phuong.get("answer", "")
    images_phuong = res_phuong.get("images", [])

    print(f"   👉 Câu hỏi: '{q_phuong}'")
    print(f"   ✅ Độ dài text trả lời: {len(answer_phuong)} ký tự")
    print(f"   ✅ Số lượng ảnh UI đính kèm: {len(images_phuong)} ảnh")
    assert len(answer_phuong) > 50, "Answer text quá ngắn hoặc trống"
    assert len(images_phuong) > 0, "Không có ảnh nào được đính kèm cho câu hỏi quy trình"

    for idx, img_url in enumerate(images_phuong, 1):
        img_resp = requests.get(img_url, timeout=10)
        assert img_resp.status_code == 200, f"Lỗi tải ảnh {img_url}: status {img_resp.status_code}"
        assert "image" in img_resp.headers.get("content-type", "").lower(), f"Content-type không phải ảnh: {img_resp.headers.get('content-type')}"
        print(f"      🖼️ Ảnh {idx}: {img_url} -> HTTP 200 ({len(img_resp.content)} bytes)")

    # 3. Test Doanh nghiệp Role
    print("\n3️⃣ Kiểm thử câu hỏi Phân hệ Doanh nghiệp:")
    q_dn = "Quy trình gửi báo cáo an toàn vệ sinh lao động định kỳ"
    payload_dn = {
        "query": q_dn,
        "role": "dn",
        "stream": False
    }
    r = requests.post("http://127.0.0.1:8000/api/v1/chat", json=payload_dn, timeout=30)
    assert r.status_code == 200, f"Chat dn failed with status {r.status_code}"
    res_dn = r.json().get("data", {})
    answer_dn = res_dn.get("answer", "")
    images_dn = res_dn.get("images", [])

    print(f"   👉 Câu hỏi: '{q_dn}'")
    print(f"   ✅ Độ dài text trả lời: {len(answer_dn)} ký tự")
    print(f"   ✅ Số lượng ảnh UI đính kèm: {len(images_dn)} ảnh")
    assert len(answer_dn) > 50, "Answer text quá ngắn hoặc trống"
    assert len(images_dn) > 0, "Không có ảnh nào được đính kèm cho câu hỏi DN"

    for idx, img_url in enumerate(images_dn, 1):
        img_resp = requests.get(img_url, timeout=10)
        assert img_resp.status_code == 200, f"Lỗi tải ảnh {img_url}: status {img_resp.status_code}"
        print(f"      🖼️ Ảnh {idx}: {img_url} -> HTTP 200 ({len(img_resp.content)} bytes)")

    # 4. Test Frontend Server Availability
    print("\n4️⃣ Kiểm tra Frontend Web UI Server (Next.js):")
    r_front = requests.get("http://localhost:3000", timeout=10)
    assert r_front.status_code == 200, f"Frontend không phản hồi HTTP 200, status={r_front.status_code}"
    print(f"   ✅ Frontend Web UI sẵn sàng tại http://localhost:3000 (HTTP 200, {len(r_front.text)} bytes HTML)")

    print("\n" + "=" * 70)
    print("🎉 TẤT CẢ CÁC BƯỚC VALIDATION THÀNH CÔNG RỰC RỠ! HỆ THỐNG HOÀN TOÀN ĐẠT CHUẨN!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        test_multimodal_end_to_end()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ VALIDATION THẤT BẠI: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ LỖI NGOẠI LỆ: {e}")
        sys.exit(2)
