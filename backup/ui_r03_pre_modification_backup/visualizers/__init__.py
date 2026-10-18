"""Aeolus Plotly visualizers package."""

from dashboard.visualizers.theme import (
    AEOLUS_PLOTLY_THEME,
    COLOR_ACCENT_GLOW,
    COLOR_ACCENT_PRIMARY,
    COLOR_APRON_REMOTE,
    COLOR_BG_CANVAS,
    COLOR_BG_ELEVATED,
    COLOR_BG_SURFACE,
    COLOR_BORDER_ACTIVE,
    COLOR_BORDER_SUBTLE,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    apply_aeolus_theme,
)
from dashboard.visualizers.timeline_chart import create_activity_timeline_figure
from dashboard.visualizers.delay_distribution_chart import create_delay_distribution_figure
from dashboard.visualizers.turn_dynamics_chart import create_turn_dynamics_figure
from dashboard.visualizers.concourse_chart import create_concourse_utilization_figure
from dashboard.visualizers.shap_charts import (
    create_shap_global_figure,
    create_shap_waterfall_figure,
)
from dashboard.visualizers.gantt_chart import create_gate_gantt_figure
from dashboard.visualizers.optimization_charts import (
    create_pareto_frontier_figure,
    create_runtime_breakdown_figure,
    create_scalability_curve_figure,
)
from dashboard.visualizers.robustness_charts import (
    create_mc_cost_distribution_figure,
    create_mc_ecdf_figure,
    create_mc_boxplot_figure,
    create_mc_convergence_figure,
)

__all__ = [
    "AEOLUS_PLOTLY_THEME",
    "COLOR_ACCENT_GLOW",
    "COLOR_ACCENT_PRIMARY",
    "COLOR_APRON_REMOTE",
    "COLOR_BG_CANVAS",
    "COLOR_BG_ELEVATED",
    "COLOR_BG_SURFACE",
    "COLOR_BORDER_ACTIVE",
    "COLOR_BORDER_SUBTLE",
    "COLOR_STATUS_ERROR",
    "COLOR_STATUS_SUCCESS",
    "COLOR_STATUS_WARNING",
    "COLOR_TEXT_MUTED",
    "COLOR_TEXT_PRIMARY",
    "COLOR_TEXT_SECONDARY",
    "apply_aeolus_theme",
    "create_activity_timeline_figure",
    "create_delay_distribution_figure",
    "create_turn_dynamics_figure",
    "create_concourse_utilization_figure",
    "create_shap_global_figure",
    "create_shap_waterfall_figure",
    "create_gate_gantt_figure",
    "create_pareto_frontier_figure",
    "create_runtime_breakdown_figure",
    "create_scalability_curve_figure",
    "create_mc_cost_distribution_figure",
    "create_mc_ecdf_figure",
    "create_mc_boxplot_figure",
    "create_mc_convergence_figure",
]
