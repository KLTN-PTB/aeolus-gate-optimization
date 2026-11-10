"""Render current phase 1/2 Markdown from audit outputs; --check never writes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"artifacts/reconciliation/phase1_2"
DOC=ROOT/"docs/reconciliation/phase1_2"


def read(name):
    return json.loads((ART/name).read_text(encoding="utf-8"))


def generate():
    req=read("requirements.json"); proposal=read("proposal_extract.json"); result={}
    lines=["# Ma trận đối chiếu yêu cầu đề cương", "",
           "Nguồn là đề CNTT-KLCN168. Mỗi dòng có trích đoạn nguyên văn và vị trí trong bản trích xuất.",
           "35 hạng mục bao gồm kỹ thuật, sản phẩm, quy trình và khuyến khích tùy chọn. Không cộng điểm tổng và điểm con để chấm điểm.", "",
           "| Mã | Yêu cầu | CLO hoặc rubric | Hiện trạng | Bằng chứng | GVHD |",
           "|---|---|---|---|---|---|"]
    for r in req:
        lines.append(f'| [{r["id"]}](#{r["id"].lower()}) | {r["title"]} | {r["rubric_reference"]} | {r["fulfillment"]} | {r["evidence_status"]} | {r["advisor_status"]} |')
    lines+=["", "PARTIAL: có triển khai/bằng chứng và còn giới hạn. NOT_EVIDENCED: chưa đủ căn cứ cho hạng mục đó.",
            "PENDING: chưa có xác nhận GVHD. NONE: chưa đề nghị điều chỉnh riêng, không có nghĩa đã duyệt.",
            "Nguồn hiện hữu chưa đủ xác minh số học: đọc 05_results.md và validation.json.", ""]
    for r in req:
        lines += [f'## {r["id"]}', "", f'**{r["title"]}** — {r["fulfillment"]}; GVHD: {r["advisor_status"]}.', "",
                  f'Mã cũ: {r["legacy_requirement"]}. Nguồn: '+", ".join(r["source_paragraphs"])+".", ""]
        lines.extend(f'> {pid}: {quote}' for pid,quote in zip(r["source_paragraphs"],r["source_quotes"]))
        lines+=["", "Triển khai: "+("; ".join(r["implementation"]) or "Chưa xác định artifact triển khai riêng")+".",
                "Bằng chứng: "+"; ".join(r["evidence"])+".",
                "Kiểm thử: "+("; ".join(r["tests"]) or "Chưa có kiểm thử hoặc biên bản riêng")+".",
                "Hành động: "+r["action"], ""]
    lines+=["## Thang điểm và lịch gốc", "",
            "Các ô của ba bảng được giữ trong [proposal_extract.json](../../../artifacts/reconciliation/phase1_2/proposal_extract.json).",
            "T1R7 chứa CLO3, điểm tổng 4,0 và điểm con. Không cộng lặp hoặc tự phân điểm khi nguồn chưa chỉ rõ.",
            "T1R13 là khuyến khích NCKH. Lịch tuần thiếu số hiển thị trong ô nguồn được giữ nguyên.", ""]
    result["01_requirements.md"]="\n".join(lines)
    result["05_results.md"]=(ART/"results_tables.md").read_text(encoding="utf-8")+"""
## Nguồn và phạm vi sử dụng

Giá trị đầy đủ và công thức: [ML](../../../artifacts/reconciliation/phase1_2/ml_metrics.json),
[MC500](../../../artifacts/reconciliation/phase1_2/mc500_audit.json),
[HPO](../../../artifacts/reconciliation/phase1_2/hpo_audit.json),
[benchmark](../../../artifacts/reconciliation/phase1_2/benchmark_audit.json),
[SHAP](../../../artifacts/reconciliation/phase1_2/shap_audit.json).
Từng nguồn có hash trong source_inventory.json. Sai lệch vài phần triệu ở CSV cũ có thể liên quan
độ chính xác dự báo hoặc phân bin; bảng hiện tại dùng phép tính ở 04_evidence_policy.md.
Chưa đủ bằng chứng thì không khẳng định nguyên nhân.

Được dùng: thống kê mô tả đúng task, population và chế độ thông tin đã ghi.
Cần thẩm định tiếp: provenance huấn luyện, tính khả dụng dữ liệu trước cutoff, fairness ngân sách,
kiểm tra toàn repo và quyết định điều chỉnh phạm vi đề.
"""
    model=read("model_identity.json"); shap=read("shap_audit.json"); val=read("validation.json")
    lines=["# Trạng thái hiện hành sau đối soát", "",
           "Mốc mã nguồn: aed54a1. Học thuật: READY_FOR_ADVISOR_REVIEW; chưa có xác nhận đổi phạm vi hoặc G13 mới.",
           f'Nhất quán nội bộ: {val["status"]}. Kết quả này không phải full regression hay chứng nhận vận hành sân bay.', "",
           "## Luồng đang chạy", "",
           "Raw Parquet → chuẩn hóa ngày sự kiện ATL → dự báo arrival/departure → ghép cặp suy diễn hoặc single-leg → dựng khoảng chiếm dụng → Greedy/CP-SAT/Hybrid → checker độc lập → lưu kết quả.",
           "Streamlit giữ kịch bản đăng ký; React/FastAPI hỗ trợ upload, benchmark bốn solver và Monte Carlo riêng.",
           "Cutoff đặc trưng là CRS_DEP_TIME − 2h. Replay dùng actual timestamps là hồi cứu, không chứng minh chất lượng ML.", "",
           "## Định danh model", "",
           "| Registry ID | Task | Status | Role | Downstream eligible |",
           "|---|---|---|---|---|"]
    for mid,r in model["registry"].items():
        lines.append(f'| {mid} | {r["task"]} | {r["status"]} | {r["selection_role"]} | {r["downstream_eligible"]} |')
    lines+=["", f'Checkpoint arrival deserialize thành {model["loaded_class"]}.',
            f'SHA-256: {model["arrival_sha256"]}.',
            "Native arrival ID là b5_ngboost_student_t (legacy_frozen). Tên P4 trong chứng nhận lịch sử thuộc một thế hệ báo cáo; registry hiện tại không coi P4 research_candidate và B5 là cùng ID có quyền ngang nhau.",
            "Departure point model là XGBoost Regressor, khác outbound calibrated classifier.",
            "Đợt này không đổi quyền registry hoặc checkpoint.", "",
            "## Khả năng nạp checkpoint", "",
            "| File | Bytes | Nạp | Loại đối tượng hoặc lỗi |", "|---|---:|---|---|"]
    for r in model["checkpoint_inventory"]:
        detail=r.get("object_type",r.get("error_type","")+": "+r.get("error",""))
        lines.append(f'| {r["path"]} | {r["bytes"]} | {r["load_status"]} | {detail.replace("|","/")} |')
    lines+=["", "Nạp được chỉ kiểm tra deserialize trên môi trường hiện tại, không chứng minh chất lượng thống kê hoặc khả năng phục vụ mọi model.", "",
            "## Các bộ thực nghiệm", "",
            "- Baseline arrival: 16.000 dòng OOF; tuned XGBoost: 1.254.518 dòng. Có pooled và macro riêng.",
            "- Departure selection 2023: 332.734 dòng; dùng đúng classifier/regressor.",
            "- G4 strict native run: 200 legs, 0 verified/inferred pairs, các turn single-leg. Không gọi là 200 rotations xác thực.",
            "- Official MC500: 500 realizations, 5.500 slots, Gaussian copula 0,45 và marginal cấu hình.",
            "- Web MC: arrival marginals độc lập, departure point giữ cố định; recourse biết toàn bộ ngày.",
            "- Replay ATL 2026: 1.500 movements = 750 occupancies, 150 contact gates mô phỏng; khác sample upload cả ngày.", "",
            "## Giới hạn nghiệm thu", "",
            f'SHAP: {shap["status"]}, departure regression; không gán cho flight upload mới.',
            "Visual QA, nhật ký nhóm, quyết định GVHD, Word/PDF/PPTX cuối và G13 nằm trong backlog.",
            "P14/G12C và current_state.yaml giữ nguyên lịch sử. Bộ này là lớp đối chiếu hiện hành, không ghi đè quyết định LOCKED.", ""]
    result["06_current_state.md"]="\n".join(lines)
    changes=[
        ("AUC bản nháp không có nguồn phù hợp","Dùng đúng task/split và phép tính mới","07_current_thesis.md; 08_defense_slides.md","ml_metrics.json"),
        ("P08 ghi macro cho phép tính pooled","Công bố riêng pooled, macro, N và fold","05_results.md","ml_metrics.json"),
        ("P08 tuned row là hằng số","Dùng full OOF 1.254.518 dòng, không so gain với subset khác","05_results.md","ml_metrics.json; hpo_audit.json"),
        ("Chain/Weather như ablation đã xác minh","Hằng số thiếu prediction lineage, bỏ gain khỏi kết luận chính","02_advisor_review.md","lineage_audit.json"),
        ("Weighted Ensemble như Stacking","Hai phương pháp khác nhau; DEV-02 chờ GVHD","01_requirements.md","lineage_audit.json"),
        ("P4 và B5 như cùng engine","Đối chiếu class deserialize, registry và native ID","06_current_state.md","model_identity.json"),
        ("Sigmoid regression như classifier","Ghi HEURISTIC_DERIVED riêng","05_results.md","ml_metrics.json"),
        ("XGBoost calibration ghi isotonic","XGBoost dùng sigmoid; LR dùng isotonic","07_current_thesis.md","scripts/train_outbound_classifiers_g3.py"),
        ("Mode A theo số pilot cũ","25,2% feasible; 682 overlaps mỗi initial solver; 0 buffer violations","05_results.md","mc500_audit.json"),
        ("C2 100% optimum hoặc B2−C2 là EVPI","499 OPTIMAL, 1 FEASIBLE; policy-to-foresight gap","08_defense_slides.md","mc500_audit.json"),
        ("CI95 được xem là cùng phép tính","Công bố Student t; CSV cũ dùng xấp xỉ 1,96","04_evidence_policy.md","mc500_audit.json"),
        ("Hybrid luôn bằng/thắng CP-SAT","Báo cáo kết quả từng run; không khái quát ngân sách","05_results.md","benchmark_audit.json"),
        ("BTS nói chung thiếu TAIL_NUM","Phát biểu theo dataset cụ thể; tail chưa xác thực rotation","07_current_thesis.md","model_identity.json; src/simulation/bts_daily_replay.py"),
        ("Median làm chứng minh lợi thế triển khai","Tách median từ eval labels; cần train-only nếu dùng deployment baseline","04_evidence_policy.md","lineage_audit.json"),
        ("Web recourse là causal online","Ghi hồi cứu biết toàn bộ ngày, khác B2 chính thức","09_demo_and_qa.md","web_dashboard/experiments.py"),
        ("Số test mọi mốc như full suite hiện tại","Giữ scope/date; G13 còn riêng","11_validation_report.md","docs/dashboard/EXPERIMENT_ACCEPTANCE.md"),
    ]
    lines=["# Nhật ký hiệu đính và nguồn kế thừa", "",
           "G9/G8/G12C và chứng nhận lịch sử được giữ nguyên. Bản sử dụng hiện tại nằm trong bộ này.",
           "Không khẳng định GVHD đã duyệt. Giá trị bị rút bỏ có thể tồn tại trong lịch sử để truy vết.", "",
           "| Nội dung trước đây | Hiện tại | Nơi sử dụng | Căn cứ |", "|---|---|---|---|"]
    lines.extend("| "+" | ".join(row)+" |" for row in changes)
    result["10_change_log.md"]="\n".join(lines)+"\n"
    refs=[p for p in proposal["paragraphs"] if p["text"].startswith("[") and p["text"].split("]",1)[0][1:].isdigit()]
    result["12_references.md"]="# Danh mục tham khảo từ đề gốc\n\n"+\
        "Trích nguyên văn từ đề, giữ tác giả, tên, DOI/URL và mã số. Có mặt trong đề không có nghĩa thông tin thư mục hoặc bài gốc đã được xác minh trực tuyến trong đợt này.\n\n"+\
        "\n\n".join(f'{p["id"]}: {p["text"]}' for p in refs)+\
        "\n\nBản G9 có danh mục khác về số lượng. Khi viết luận văn chỉ dẫn nguồn thực sự sử dụng; không biến kết quả nội bộ thành kết luận của bài báo được trích.\n"
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--check",action="store_true")
    args=parser.parse_args();failures=[]
    for name,content in generate().items():
        path=DOC/name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8-sig")!=content:failures.append(name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding="utf-8")
    if failures:
        print("Reports out of date: "+", ".join(failures));return 1
    print("Report comparison passed." if args.check else "Published current reports.");return 0


if __name__=="__main__":
    raise SystemExit(main())
