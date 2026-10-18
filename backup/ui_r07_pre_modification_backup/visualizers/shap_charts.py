"""CHART-05 & CHART-06: TreeSHAP Explainability Visualizers.

CHART-05: Global feature importance ranking (mean absolute SHAP values).
CHART-06: Local single-flight waterfall plot with additive attribution validation.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import plotly.graph_objects as go

from dashboard.visualizers.theme import (
    COLOR_ACCENT_PRIMARY,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    apply_aeolus_theme,
)


FEATURE_LABEL_MAP: Dict[str, str] = {
    "numeric__scheduled_departure_hour": "Giờ khởi hành theo lịch (CRS Hour)",
    "numeric__CRS_ELAPSED_TIME": "Thời gian bay dự kiến (CRS Elapsed)",
    "categorical__OP_CARRIER": "Hãng hàng không (Carrier)",
    "numeric__calendar_month": "Tháng trong năm (Calendar Month)",
    "numeric__day_of_week": "Thứ trong tuần (Day of Week)",
    "arr_delay_prior_network": "Trễ mạng lưới tích lũy (Prior Delay)",
    "carrier_arrival_trend": "Xu hướng khai thác của hãng (Carrier Trend)",
    "taxi_in_historical_mean": "Thời gian lăn bánh trung bình (Taxi-in Mean)",
}


def create_shap_global_figure(
    importance_df: Optional[pd.DataFrame] = None,
    top_n: int = 10,
) -> go.Figure:
    """Generate global TreeSHAP feature importance horizontal bar chart (CHART-05).

    Args:
        importance_df: DataFrame with 'feature' and 'mean_abs_shap' / 'mean_abs_shap_minutes'.
        top_n: Maximum features to display (default 10).

    Returns:
        go.Figure: Plotly figure conforming to CHART-05 contract.
    """
    fig = go.Figure()

    if importance_df is None or importance_df.empty:
        fig.add_annotation(
            text="Chưa có dữ liệu tầm quan trọng tính năng toàn cục",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(
            title={"text": "Xếp hạng Tầm quan trọng Tính năng Toàn cục SHAP (CHART-05)", "x": 0.05},
        )
        return apply_aeolus_theme(fig)

    col_val = "mean_abs_shap" if "mean_abs_shap" in importance_df.columns else "mean_abs_shap_minutes"
    df_sorted = importance_df.sort_values(by=col_val, ascending=True).tail(top_n)

    features = [FEATURE_LABEL_MAP.get(f, f.replace("numeric__", "").replace("categorical__", "")) for f in df_sorted["feature"]]
    values = df_sorted[col_val].tolist()

    hover_texts = [
        f"<b>{feat}</b><br>Tác động trung bình: +{val:.2f} phút trễ tuyệt đối"
        for feat, val in zip(features, values)
    ]

    fig.add_trace(
        go.Bar(
            y=features,
            x=values,
            orientation="h",
            marker_color=COLOR_ACCENT_PRIMARY,
            hovertext=hover_texts,
            hoverinfo="text",
            text=[f"{v:.2f}m" for v in values],
            textposition="outside",
        )
    )

    fig.update_layout(
        title={
            "text": "<b>XẾP HẠNG TÍNH NĂNG TOÀN CỤC SHAP (CHART-05)</b>",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis_title="Tác động Trung bình Tuyệt đối (|SHAP|, Phút)",
        yaxis_title="",
        height=360,
        showlegend=False,
    )

    return apply_aeolus_theme(fig)


def create_shap_waterfall_figure(
    case_study: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """Generate local single-flight TreeSHAP waterfall plot (CHART-06).

    Enforces scientific attribution validation:
    base_expected_value + sum(attributions) == reconstructed_prediction (± 0.1m).

    Args:
        case_study: Single case study dictionary from shap_case_studies.json.

    Returns:
        go.Figure: Plotly figure conforming to CHART-06 contract.
    """
    fig = go.Figure()

    if not case_study:
        fig.add_annotation(
            text="Chọn chuyến bay để xem phân rã đóng góp tính năng SHAP cục bộ",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": COLOR_TEXT_MUTED},
        )
        fig.update_layout(
            title={"text": "Thác nước Đóng góp SHAP Cục bộ (CHART-06)", "x": 0.05},
        )
        return apply_aeolus_theme(fig)

    meta = case_study.get("flight_metadata", {})
    flight_id = f"{meta.get('carrier', 'DL')}{meta.get('flight_num', '1024')}"
    case_type = case_study.get("case_type", "Chuyến bay")
    base_val = float(case_study.get("base_expected_value_minutes", 0.0))
    pred_val = float(case_study.get("model_predicted_delay_minutes", 0.0))
    attributions = case_study.get("feature_attributions_ordered", [])

    # Validate attribution sum
    attr_sum = sum(float(a.get("attribution_minutes", 0.0)) for a in attributions)
    reconstructed = base_val + attr_sum
    is_valid_sum = abs(reconstructed - pred_val) < 0.1

    # Build waterfall steps
    x_labels = ["Kỳ vọng nền E[f(x)]"]
    y_values = [base_val]
    measures = ["absolute"]
    text_labels = [f"{base_val:+.1f}m"]

    for item in attributions:
        feat_name = item.get("feature", "feature")
        clean_name = FEATURE_LABEL_MAP.get(feat_name, feat_name.replace("numeric__", "").replace("categorical__", ""))
        val = float(item.get("attribution_minutes", 0.0))
        x_labels.append(clean_name)
        y_values.append(val)
        measures.append("relative")
        text_labels.append(f"{val:+.2f}m")

    # Final prediction total
    x_labels.append(f"Dự báo cuối ({flight_id})")
    y_values.append(pred_val)
    measures.append("total")
    text_labels.append(f"{pred_val:+.1f}m")

    fig.add_trace(
        go.Waterfall(
            name="SHAP Attribution",
            orientation="v",
            measure=measures,
            x=x_labels,
            y=y_values,
            text=text_labels,
            textposition="outside",
            connector={"line": {"color": "#3B5780"}},
            decreasing={"marker": {"color": COLOR_STATUS_SUCCESS}},   # Reduces delay
            increasing={"marker": {"color": COLOR_STATUS_ERROR}},     # Increases delay
            totals={"marker": {"color": COLOR_ACCENT_PRIMARY}},
        )
    )

    validation_note = "✓ Tổng SHAP khớp chính xác" if is_valid_sum else "⚠️ Sai lệch tổng SHAP"

    fig.update_layout(
        title={
            "text": f"<b>THÁC NƯỚC SHAP CỤC BỘ — {flight_id} ({case_type})</b> [{validation_note}]",
            "x": 0.02,
            "font": {"size": 14, "color": COLOR_TEXT_PRIMARY},
        },
        xaxis_title="",
        yaxis_title="Độ trễ Dự báo (Phút)",
        height=360,
        showlegend=False,
    )

    return apply_aeolus_theme(fig)
