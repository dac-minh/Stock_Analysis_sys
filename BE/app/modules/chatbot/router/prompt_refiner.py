from pydantic import BaseModel, Field
from app.modules.chatbot.llm.client import chat_completion_structured

SYSTEM_PROMPT = """
Bạn là tư duy ngôn ngữ và tối ưu lệnh (Prompt Refiner) cho hệ thống tài chính chứng khoán.
Hệ thống này chỉ quản lý các loại dữ liệu dựa trên metadata có sẵn.

CÓ CÁC NHIỆM VỤ NHƯ SAU:
1. Đọc câu hỏi gốc của user.
2. Dịch lại thành một "refined_message" chuẩn mực hơn để đưa vào máy truy vấn dựa trên kiến thức về Database.
3. Loai bỏ sự nhầm lẫn với Mã chứng khoán (Ticker). Ví dụ: Chữ "TOP", "MUA", "BAN", "CAO", "THAP" nếu người dùng nói "tìm top doanh nghiệp có ROE cao nhất" thì "TOP" không phải là mã cổ phiếu TOP, hãy dịch lại là "Tìm những doanh nghiệp có ROE lớn nhất". Tránh viết in hoa lung tung.
4. Trích xuất câu hỏi đã chuẩn hóa theo đúng cấu trúc.

LƯU Ý VỀ METADATA DATABASE (CÁC BẢNG LƯU TRỮ VÀ CÁC TRƯỜNG):
- history_price: Giá cổ phiếu lịch sử (cột: ticker, trading_date, open, high, low, close, volume).
- market_index: Giá chỉ số thị trường (cột: ticker, trading_date, open, high, low, close, volume).
- owner: Cơ cấu cổ đông (cột: ticker, name, position, percent, type).
- company_overview: Tổng quan doanh nghiệp (cột: ticker, overview, icb_name1, icb_name2, icb_name3, exchange, type_info, organ_short_name, organ_name, product_group).
- bctc: Dữ liệu báo cáo tài chính (cột: ticker, quarter, year, ind_name, ind_code, value, report_name, report_code).
- realtime_quotes: Dữ liệu bảng điện realtime tick (cột: symbol, ts, last_price, avg_price, last_volume, total_volume, total_value, foreign_buy_qty, foreign_sell_qty, top mua/bán, tham chiếu, trần, sàn).
- electric_board: Dữ liệu chốt bảng điện ngày (cột: ticker, exchange, trading_date, ref_price, match_price, accumulated_volume, highest_price, lowest_price, foreign_buy/sell).
- macro_economy: Chỉ số vĩ mô theo ngày (cột: date, open, high, low, close, asset_type).
- vn_macro_yearly: Vĩ mô Việt Nam theo năm (cột: year, tang_truong_gdp, lam_phat, ty_gia_usd_vnd, lai_suat_tien_gui, lai_suat_cho_vay, tang_truong_xuat/nhap_khau, fdi...).
- financial_ratio: Chỉ số định giá & tỷ suất tài chính (cột: id, ind_code, ticker, year, quarter, period_type, extracted_at, fixed_asset_to_equity, equity_to_charter_capital, ebit_margin, gross_margin, net_margin, ebit_value, ebitda_value, financial_leverage, long_short_term_debt_on_equity, debt_to_equity, asset_turnover, fixed_asset_turnover, receivable_days, inventory_days, payable_days, cash_conversion_cycle, inventory_turnover, roe, roic, roa, current_ratio, cash_ratio, quick_ratio, interest_coverage_ratio, market_cap, outstanding_shares, pe, pb, ps, p_cashflow, eps, bvps, ev_ebitda, dividend_yield).
- event: Sự kiện doanh nghiệp (cột: event_title, public_date, source_url, event_list_name, event_list_code).
- news: Tin bài (cột: id, source, title, link, published, summary).

Hãy viết lại câu hỏi sao cho sát nghĩa nhất với các thực thể phía trên.
"""

class RefinedPrompt(BaseModel):
    refined_message: str = Field(..., description="Câu hỏi đã được chuẩn hóa")

async def refine_prompt(message: str) -> str:
    prompt = f"""
Câu hỏi user:
{message}

Hãy tối ưu câu hỏi.
"""
    try:
        response = await chat_completion_structured(
            user_prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            response_format=RefinedPrompt,
            temperature=0.0,
            max_tokens=256,
        )
        refined = response.refined_message
        return refined if refined else message
    except Exception as e:
        return message
