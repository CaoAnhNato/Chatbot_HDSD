import re
from typing import List, Optional, Dict
from app.models.chat import QuickActionChip
from app.models.chunk import DocumentChunk
from app.core.logger import logger


class SuggestionService:
    """
    Context-Aware Follow-up Question Suggestion Service.
    Automatically generates 3 highly relevant next-step action chips
    based on the current business module and user query.
    """

    SUGGESTION_MATRIX: Dict[str, List[Dict[str, str]]] = {
        "ĐĂNG KÝ": [
            {
                "id": "sug_reg_1",
                "label": "⏱️ Khi nào được kích hoạt?",
                "query_text": "Tài khoản sau khi đăng ký bao lâu thì được Sở kích hoạt để đăng nhập?"
            },
            {
                "id": "sug_reg_2",
                "label": "🔑 Mã số thuế làm tài khoản?",
                "query_text": "Mã số thuế có phải là tài khoản đăng nhập của doanh nghiệp không?"
            },
            {
                "id": "sug_reg_3",
                "label": "🚀 Hướng dẫn đăng nhập",
                "query_text": "Hướng dẫn các bước đăng nhập hệ thống sau khi đã đăng ký tài khoản"
            },
            {
                "id": "sug_reg_4",
                "label": "🏢 Đổi thông tin doanh nghiệp",
                "query_text": "Làm thế nào để thay đổi thông tin doanh nghiệp?"
            }
        ],
        "ĐĂNG NHẬP": [
            {
                "id": "sug_login_1",
                "label": "🔑 Đổi mật khẩu tài khoản",
                "query_text": "Làm thế nào để đổi mật khẩu tài khoản doanh nghiệp?"
            },
            {
                "id": "sug_login_2",
                "label": "🏢 Cập nhật thông tin DN",
                "query_text": "Hướng dẫn cập nhật thông tin doanh nghiệp sau khi đăng nhập"
            },
            {
                "id": "sug_login_3",
                "label": "⚠️ Hướng dẫn nộp báo cáo TNLĐ",
                "query_text": "Hướng dẫn nộp báo cáo tai nạn lao động định kỳ"
            },
            {
                "id": "sug_login_4",
                "label": "📞 Quên mật khẩu/Không vào được",
                "query_text": "Không đăng nhập được hoặc quên mật khẩu thì liên hệ ai hỗ trợ?"
            }
        ],
        "THAY ĐỔI MẬT KHẨU": [
            {
                "id": "sug_pwd_1",
                "label": "🏢 Đổi thông tin doanh nghiệp",
                "query_text": "Hướng dẫn thay đổi thông tin doanh nghiệp"
            },
            {
                "id": "sug_pwd_2",
                "label": "⚠️ Nộp báo cáo tai nạn lao động",
                "query_text": "Hướng dẫn nộp báo cáo tai nạn lao động định kỳ"
            },
            {
                "id": "sug_pwd_3",
                "label": "🛡️ Nộp báo cáo An toàn VSLĐ",
                "query_text": "Hướng dẫn nộp báo cáo định kỳ An toàn vệ sinh lao động"
            },
            {
                "id": "sug_pwd_4",
                "label": "📞 Hotline & Zalo hỗ trợ",
                "query_text": "Cho tôi thông tin hotline và zalo hỗ trợ kỹ thuật"
            }
        ],
        "THAY ĐỔI THÔNG TIN DOANH NGHIỆP": [
            {
                "id": "sug_dn_1",
                "label": "💾 Cách lưu lại thông tin vừa sửa",
                "query_text": "Sau khi sửa thông tin doanh nghiệp làm sao để lưu lại trên hệ thống?"
            },
            {
                "id": "sug_dn_2",
                "label": "⚠️ Hướng dẫn nộp báo cáo TNLĐ",
                "query_text": "Hướng dẫn nộp báo cáo tai nạn lao động định kỳ"
            },
            {
                "id": "sug_dn_3",
                "label": "🛡️ Hướng dẫn nộp báo cáo ATVSLĐ",
                "query_text": "Hướng dẫn nộp báo cáo An toàn vệ sinh lao động"
            },
            {
                "id": "sug_dn_4",
                "label": "📊 Xem thống kê số liệu",
                "query_text": "Làm thế nào để xem biểu đồ thống kê tai nạn lao động?"
            }
        ],
        "BÁO CÁO ĐỊNH KỲ - 1. Tai nạn lao động": [
            {
                "id": "sug_tnld_1",
                "label": "🔢 Không có tai nạn điền số mấy?",
                "query_text": "Mục Trợ cấp theo khoản 2 điều 39 luật ATVSLĐ nếu không có thì nhập số mấy?"
            },
            {
                "id": "sug_tnld_2",
                "label": "💰 Đơn vị Tổng quỹ lương là gì?",
                "query_text": "Trường Tổng quỹ lương khi báo cáo TNLĐ nhập đơn vị là Triệu đồng hay gì?"
            },
            {
                "id": "sug_tnld_3",
                "label": "🔒 Đã gửi rồi có sửa được không?",
                "query_text": "Tôi vừa bấm Gửi báo cáo TNLĐ lên Sở nhưng phát hiện sai số liệu, có sửa lại được không?"
            },
            {
                "id": "sug_tnld_4",
                "label": "📄 Quy trình in & scan báo cáo",
                "query_text": "Cho tôi hỏi làm sao để xuất hoặc in báo cáo TNLĐ trình ký đóng mộc?"
            }
        ],
        "BÁO CÁO ĐỊNH KỲ - 2. An toàn vệ sinh lao động": [
            {
                "id": "sug_atvsld_1",
                "label": "🔘 Nút Gửi báo cáo vs Hủy bỏ?",
                "query_text": "Trong màn hình xem báo cáo ATVSLĐ, nút 'Gửi báo cáo' khác gì với nút 'Hủy bỏ'?"
            },
            {
                "id": "sug_atvsld_2",
                "label": "🔒 Báo cáo Chờ tiếp nhận sửa sao?",
                "query_text": "Báo cáo ATVSLĐ chuyển trạng thái Chờ tiếp nhận thì có sửa được không?"
            },
            {
                "id": "sug_atvsld_3",
                "label": "📺 Video hướng dẫn khai báo",
                "query_text": "Có video hướng dẫn cách khai báo An toàn vệ sinh lao động không?"
            },
            {
                "id": "sug_atvsld_4",
                "label": "📞 Liên hệ mở khóa báo cáo",
                "query_text": "Liên hệ ai để được hỗ trợ mở khóa báo cáo khi gửi nhầm số liệu?"
            }
        ],
        "THỐNG KÊ": [
            {
                "id": "sug_stat_1",
                "label": "📈 Xem biểu đồ theo năm",
                "query_text": "Làm thế nào để doanh nghiệp xem lại biểu đồ thống kê các vụ tai nạn lao động theo từng năm?"
            },
            {
                "id": "sug_stat_2",
                "label": "🖨️ Cách in / xuất báo cáo",
                "query_text": "Làm thế nào để in hoặc xuất file báo cáo từ hệ thống?"
            },
            {
                "id": "sug_stat_3",
                "label": "🛡️ Nộp báo cáo ATVSLĐ định kỳ",
                "query_text": "Hướng dẫn nộp báo cáo định kỳ An toàn vệ sinh lao động"
            },
            {
                "id": "sug_stat_4",
                "label": "⚠️ Nộp báo cáo TNLĐ định kỳ",
                "query_text": "Hướng dẫn nộp báo cáo tai nạn lao động định kỳ"
            }
        ],
        "THAY ĐỔI THÔNG TIN CÁ NHÂN": [
            {
                "id": "sug_p_user_1",
                "label": "💾 Cách lưu thông tin",
                "query_text": "Sau khi đổi thông tin cá nhân cán bộ thì bấm nút gì để lưu?"
            },
            {
                "id": "sug_p_user_2",
                "label": "🔑 Hướng dẫn đổi mật khẩu",
                "query_text": "Làm sao để đổi mật khẩu tài khoản đang đăng nhập?"
            },
            {
                "id": "sug_p_user_3",
                "label": "👥 Quản lý tài khoản tuyến dưới",
                "query_text": "Giải đáp chức năng tài khoản phường xã gồm những thao tác nào?"
            },
            {
                "id": "sug_p_user_4",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Quy trình phường/xã khai báo vụ tai nạn lao động ngay khi mới xảy ra trên địa bàn"
            }
        ],
        "TỔNG QUAN CHỨC NĂNG TÀI KHOẢN PHƯỜNG/XÃ": [
            {
                "id": "sug_p_acc_1",
                "label": "➕ Tạo mới tài khoản",
                "query_text": "Làm sao để tạo tài khoản mới cho phường xã tuyến dưới?"
            },
            {
                "id": "sug_p_acc_2",
                "label": "✏️ Chỉnh sửa tài khoản",
                "query_text": "Cách sửa thông tin tài khoản tuyến dưới đã tạo?"
            },
            {
                "id": "sug_p_acc_3",
                "label": "🔓 Khôi phục mật khẩu",
                "query_text": "Làm sao để lấy lại mật khẩu cho tài khoản tuyến dưới khi bị quên?"
            },
            {
                "id": "sug_p_acc_4",
                "label": "🗑️ Xóa tài khoản",
                "query_text": "Làm cách nào để xóa tài khoản phường xã tuyến dưới?"
            }
        ],
        "TẠO MỚI TÀI KHOẢN PHƯỜNG/XÃ": [
            {
                "id": "sug_p_create_1",
                "label": "✏️ Chỉnh sửa tài khoản vừa tạo",
                "query_text": "Cách sửa thông tin tài khoản tuyến dưới đã tạo?"
            },
            {
                "id": "sug_p_create_2",
                "label": "🔓 Khôi phục mật khẩu tuyến dưới",
                "query_text": "Cách reset khôi phục mật khẩu cho tài khoản phường xã?"
            },
            {
                "id": "sug_p_create_3",
                "label": "🗑️ Xóa tài khoản tuyến dưới",
                "query_text": "Hướng dẫn gỡ bỏ tài khoản không còn sử dụng ra khỏi hệ thống"
            }
        ],
        "CHỈNH SỬA TÀI KHOẢN PHƯỜNG/XÃ": [
            {
                "id": "sug_p_edit_1",
                "label": "➕ Tạo thêm tài khoản mới",
                "query_text": "Làm sao để tạo tài khoản mới cho phường xã tuyến dưới?"
            },
            {
                "id": "sug_p_edit_2",
                "label": "🔓 Reset mật khẩu tuyến dưới",
                "query_text": "Làm sao để lấy lại mật khẩu cho tài khoản tuyến dưới khi bị quên?"
            },
            {
                "id": "sug_p_edit_3",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Cách báo cáo tai nạn lao động đột xuất không theo HĐLĐ như thế nào?"
            }
        ],
        "KHÔI PHỤC MẬT KHẨU TÀI KHOẢN PHƯỜNG/XÃ": [
            {
                "id": "sug_p_reset_1",
                "label": "✏️ Sửa thông tin tài khoản",
                "query_text": "Cách sửa thông tin tài khoản tuyến dưới đã tạo?"
            },
            {
                "id": "sug_p_reset_2",
                "label": "🗑️ Xóa tài khoản không dùng",
                "query_text": "Làm cách nào để xóa tài khoản phường xã tuyến dưới?"
            },
            {
                "id": "sug_p_reset_3",
                "label": "📞 Hotline hỗ trợ kỹ thuật",
                "query_text": "Cho tôi thông tin hotline hỗ trợ kỹ thuật"
            }
        ],
        "XÓA TÀI KHOẢN PHƯỜNG/XÃ": [
            {
                "id": "sug_p_del_1",
                "label": "➕ Cấp mới tài khoản thay thế",
                "query_text": "Hướng dẫn cách cấp mới tài khoản cho đơn vị trực thuộc"
            },
            {
                "id": "sug_p_del_2",
                "label": "📊 Báo cáo TNLĐ định kỳ",
                "query_text": "Làm sao để phường xã khai báo tổng số vụ TNLĐ định kỳ?"
            },
            {
                "id": "sug_p_del_3",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Quy trình phường/xã khai báo vụ tai nạn lao động ngay khi mới xảy ra trên địa bàn"
            }
        ],
        "BÁO CÁO TAI NẠN LAO ĐỘNG ĐỊNH KỲ KHÔNG THEO HĐLĐ": [
            {
                "id": "sug_p_dinhky_1",
                "label": "🔢 Lưu ý công thức số liệu",
                "query_text": "Các quy tắc và lưu ý số liệu khi khai báo tổng số vụ TNLĐ định kỳ là gì?"
            },
            {
                "id": "sug_p_dinhky_2",
                "label": "💼 Phân loại theo nghề nghiệp",
                "query_text": "Cách nhập chi tiết phân loại theo nghề nghiệp khi báo cáo TNLĐ định kỳ?"
            },
            {
                "id": "sug_p_dinhky_3",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Cách báo cáo tai nạn lao động đột xuất không theo HĐLĐ như thế nào?"
            },
            {
                "id": "sug_p_dinhky_4",
                "label": "📤 Cách gửi báo cáo lên Sở",
                "query_text": "Làm sao để gửi báo cáo tai nạn lao động định kỳ lên cho Sở?"
            }
        ],
        "BÁO CÁO TAI NẠN LAO ĐỘNG ĐỘT XUẤT KHÔNG THEO HĐLĐ": [
            {
                "id": "sug_p_dotxuat_1",
                "label": "👤 Thêm & Xóa nạn nhân",
                "query_text": "Làm sao để thêm mới hoặc xóa thông tin nạn nhân trong báo cáo TNLĐ đột xuất?"
            },
            {
                "id": "sug_p_dotxuat_2",
                "label": "📎 Dung lượng tối đa file đính kèm?",
                "query_text": "Kích thước tối đa của file đính kèm trong báo cáo TNLĐ đột xuất là bao nhiêu MB?"
            },
            {
                "id": "sug_p_dotxuat_3",
                "label": "📊 Báo cáo TNLĐ định kỳ",
                "query_text": "Hướng dẫn báo cáo tai nạn lao động định kỳ cho người không có HĐLĐ"
            },
            {
                "id": "sug_p_dotxuat_4",
                "label": "📞 Hotline hỗ trợ khẩn cấp",
                "query_text": "Cho tôi thông tin hotline hỗ trợ kỹ thuật"
            }
        ],
        "LIÊN HỆ HỖ TRỢ": [
            {
                "id": "sug_help_1",
                "label": "🕒 Khung giờ tổng đài làm việc",
                "query_text": "Tổng đài hỗ trợ kỹ thuật làm việc vào những khung giờ nào trong tuần?"
            },
            {
                "id": "sug_help_2",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Quy trình phường/xã khai báo vụ tai nạn lao động ngay khi mới xảy ra trên địa bàn"
            },
            {
                "id": "sug_help_3",
                "label": "🔑 Hướng dẫn đổi mật khẩu",
                "query_text": "Làm sao để đổi mật khẩu tài khoản đang đăng nhập?"
            },
            {
                "id": "sug_help_4",
                "label": "👥 Quản lý tài khoản tuyến dưới",
                "query_text": "Giải đáp chức năng tài khoản phường xã gồm những thao tác nào?"
            }
        ],
        "DEFAULT": [
            {
                "id": "sug_def_1",
                "label": "🚨 Báo cáo TNLĐ đột xuất",
                "query_text": "Quy trình phường/xã khai báo vụ tai nạn lao động ngay khi mới xảy ra trên địa bàn"
            },
            {
                "id": "sug_def_2",
                "label": "📊 Báo cáo TNLĐ định kỳ",
                "query_text": "Hướng dẫn báo cáo tai nạn lao động định kỳ cho người không có HĐLĐ"
            },
            {
                "id": "sug_def_3",
                "label": "👥 Quản lý tài khoản tuyến dưới",
                "query_text": "Giải đáp chức năng tài khoản phường xã gồm những thao tác nào?"
            },
            {
                "id": "sug_def_4",
                "label": "📞 Hotline hỗ trợ kỹ thuật",
                "query_text": "Cho tôi thông tin hotline hỗ trợ kỹ thuật"
            }
        ]
    }

    def get_suggested_chips(
        self,
        query: str,
        target_module: Optional[str] = None,
        primary_chunk: Optional[DocumentChunk] = None,
        limit: int = 3
    ) -> List[QuickActionChip]:
        """
        Determines 3 suggested follow-up question action chips
        based on active target module and query semantics.
        """
        active_module = target_module
        if not active_module and primary_chunk and primary_chunk.metadata:
            active_module = primary_chunk.metadata.module or primary_chunk.metadata.section_title

        # Normalize module key
        matched_key = "DEFAULT"
        if active_module:
            for key in self.SUGGESTION_MATRIX:
                if key == active_module or key in active_module or active_module in key:
                    matched_key = key
                    break

        candidate_list = self.SUGGESTION_MATRIX.get(matched_key, self.SUGGESTION_MATRIX["DEFAULT"])

        # Filter out questions that are too semantically close to current user query
        norm_query = query.lower().strip()
        filtered_chips: List[QuickActionChip] = []

        for item in candidate_list:
            item_q = item["query_text"].lower()
            # Simple keyword overlap check to prevent suggesting the exact same question
            common_words = set(w for w in item_q.split() if len(w) > 3).intersection(
                set(w for w in norm_query.split() if len(w) > 3)
            )
            is_same_intent = len(common_words) >= 4 or item_q in norm_query or norm_query in item_q

            if not is_same_intent:
                filtered_chips.append(QuickActionChip(
                    id=item["id"],
                    label=item["label"],
                    query_text=item["query_text"]
                ))
            if len(filtered_chips) >= limit:
                break

        # Fallback to default candidates if fewer than limit
        if len(filtered_chips) < limit:
            for item in self.SUGGESTION_MATRIX["DEFAULT"]:
                if not any(c.id == item["id"] for c in filtered_chips):
                    filtered_chips.append(QuickActionChip(
                        id=item["id"],
                        label=item["label"],
                        query_text=item["query_text"]
                    ))
                if len(filtered_chips) >= limit:
                    break

        return filtered_chips[:limit]


suggestion_service = SuggestionService()
