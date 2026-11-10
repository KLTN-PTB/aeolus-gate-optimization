"""Positive Semi-Definite (PSD) Validation and Projection Engine.

Protocol: docs/Aeolus_Probabilistic_Core_Arrival_Protocol.md - Sections 13, 14
Features:
1. Full diagnostic calculation BEFORE correction:
   - min eigenvalue
   - negative eigenvalue count
   - sub-threshold eigenvalue count
   - matrix symmetry and condition number
2. Explicit spectral projection to PSD cone:
   - eigenvalue clipping to min_eigenvalue
   - correlation re-normalization (unit diagonal, [-1, 1] range)
3. Separate tracking of raw and corrected matrices.
4. Quantitative distortion reporting:
   - Frobenius norm distortion: ||R_corr - R_raw||_F
   - Max absolute element distortion: max |R_corr - R_raw|
   - Relative Frobenius distortion: ||R_corr - R_raw||_F / ||R_raw||_F
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from src.models.probabilistic.contracts import ProbabilisticContractViolation

MIN_PSD_EIGENVALUE: float = 1e-6


@dataclass(frozen=True)
class PSDDiagnostic:
    """Detailed diagnostics of matrix spectral properties and PSD projection."""

    matrix_dimension: int
    raw_min_eigenvalue: float
    raw_negative_eigenvalue_count: int
    raw_subthreshold_eigenvalue_count: int
    raw_is_psd: bool
    raw_symmetry_error: float
    corrected_min_eigenvalue: float
    frobenius_distortion: float
    max_absolute_distortion: float
    relative_frobenius_distortion: float
    was_correction_applied: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert diagnostic to dictionary."""
        return {
            "matrix_dimension": self.matrix_dimension,
            "raw_min_eigenvalue": float(self.raw_min_eigenvalue),
            "raw_negative_eigenvalue_count": int(self.raw_negative_eigenvalue_count),
            "raw_subthreshold_eigenvalue_count": int(self.raw_subthreshold_eigenvalue_count),
            "raw_is_psd": bool(self.raw_is_psd),
            "raw_symmetry_error": float(self.raw_symmetry_error),
            "corrected_min_eigenvalue": float(self.corrected_min_eigenvalue),
            "frobenius_distortion": float(self.frobenius_distortion),
            "max_absolute_distortion": float(self.max_absolute_distortion),
            "relative_frobenius_distortion": float(self.relative_frobenius_distortion),
            "was_correction_applied": bool(self.was_correction_applied),
        }


def validate_and_project_psd(
    matrix: np.ndarray,
    *,
    min_eigenvalue: float = MIN_PSD_EIGENVALUE,
    is_correlation: bool = True,
) -> tuple[np.ndarray, PSDDiagnostic]:
    """Validate spectral properties and project to nearest PSD matrix if needed.

    Keeps raw and corrected matrices separate and calculates exact distortion metrics.

    Args:
        matrix: 2D square matrix of shape (N, N).
        min_eigenvalue: Minimum eigenvalue floor (default 1e-6).
        is_correlation: Whether the matrix must have unit diagonal and correlation bounds.

    Returns:
        (corrected_matrix, diagnostic)
    """
    raw = np.asarray(matrix, dtype=np.float64)
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1]:
        raise ProbabilisticContractViolation(
            f"Matrix must be square 2D array, got shape {raw.shape}"
        )

    n = raw.shape[0]
    if n == 0:
        raise ProbabilisticContractViolation("Matrix cannot be empty (0x0)")

    if n == 1:
        # Scalar 1x1 case
        diag_val = 1.0 if is_correlation else float(max(raw[0, 0], min_eigenvalue))
        corrected = np.array([[diag_val]], dtype=np.float64)
        raw_val = float(raw[0, 0])
        dist = abs(diag_val - raw_val)
        diagnostic = PSDDiagnostic(
            matrix_dimension=1,
            raw_min_eigenvalue=raw_val,
            raw_negative_eigenvalue_count=1 if raw_val < -1e-12 else 0,
            raw_subthreshold_eigenvalue_count=1 if raw_val < min_eigenvalue else 0,
            raw_is_psd=raw_val >= -1e-12,
            raw_symmetry_error=0.0,
            corrected_min_eigenvalue=diag_val,
            frobenius_distortion=dist,
            max_absolute_distortion=dist,
            relative_frobenius_distortion=dist / max(abs(raw_val), 1e-12),
            was_correction_applied=bool(dist > 1e-12),
        )
        return corrected, diagnostic

    # 1. Symmetry check and symmetrization
    symmetry_error = float(np.max(np.abs(raw - raw.T)))
    sym = 0.5 * (raw + raw.T)

    # 2. Spectral analysis BEFORE correction
    raw_eigvals = np.linalg.eigvalsh(sym)
    raw_min_eig = float(np.min(raw_eigvals))
    raw_neg_count = int(np.sum(raw_eigvals < -1e-12))
    raw_subthresh_count = int(np.sum(raw_eigvals < min_eigenvalue))
    raw_is_psd = bool(raw_neg_count == 0)

    # Check if correction is needed
    needs_correction = (
        (raw_min_eig < min_eigenvalue)
        or (symmetry_error > 1e-12)
        or (is_correlation and not np.allclose(np.diag(sym), 1.0, atol=1e-12))
    )

    if not needs_correction:
        # Matrix is already strictly PSD, symmetric, and unit-diagonal
        corrected = sym.copy()
        if is_correlation:
            np.fill_diagonal(corrected, 1.0)
        diagnostic = PSDDiagnostic(
            matrix_dimension=n,
            raw_min_eigenvalue=raw_min_eig,
            raw_negative_eigenvalue_count=0,
            raw_subthreshold_eigenvalue_count=0,
            raw_is_psd=True,
            raw_symmetry_error=symmetry_error,
            corrected_min_eigenvalue=raw_min_eig,
            frobenius_distortion=0.0,
            max_absolute_distortion=0.0,
            relative_frobenius_distortion=0.0,
            was_correction_applied=False,
        )
        return corrected, diagnostic

    # 3. Explicit Spectral Projection
    eigvals, eigvecs = np.linalg.eigh(sym)
    clipped_eigvals = np.maximum(eigvals, min_eigenvalue)
    psd_proj = eigvecs @ (clipped_eigvals[:, None] * eigvecs.T)
    psd_proj = 0.5 * (psd_proj + psd_proj.T)

    if is_correlation:
        # Re-normalize to unit diagonal: D^(-1/2) * P * D^(-1/2)
        d = np.sqrt(np.maximum(np.diag(psd_proj), 1e-12))
        corr_proj = psd_proj / np.outer(d, d)
        np.fill_diagonal(corr_proj, 1.0)
        corr_proj = np.clip(corr_proj, -1.0, 1.0)
        corr_proj = 0.5 * (corr_proj + corr_proj.T)

        # Check if re-normalization dipped minimum eigenvalue below threshold
        corr_eigvals = np.linalg.eigvalsh(corr_proj)
        if np.min(corr_eigvals) < min_eigenvalue:
            # Higham (2002) step 2: project again with small shrinkage
            alpha = min_eigenvalue / max(np.max(corr_eigvals), 1.0)
            corr_proj = (1.0 - alpha) * corr_proj + alpha * np.eye(n)
            np.fill_diagonal(corr_proj, 1.0)

        corrected = corr_proj
    else:
        corrected = psd_proj

    # 4. Compute exact distortion metrics
    diff = corrected - raw
    frobenius_distortion = float(np.linalg.norm(diff, ord="fro"))
    raw_norm = float(np.linalg.norm(raw, ord="fro"))
    rel_frobenius_distortion = float(frobenius_distortion / max(raw_norm, 1e-12))
    max_abs_distortion = float(np.max(np.abs(diff)))

    corrected_eigvals = np.linalg.eigvalsh(corrected)
    corr_min_eig = float(np.min(corrected_eigvals))

    diagnostic = PSDDiagnostic(
        matrix_dimension=n,
        raw_min_eigenvalue=raw_min_eig,
        raw_negative_eigenvalue_count=raw_neg_count,
        raw_subthreshold_eigenvalue_count=raw_subthresh_count,
        raw_is_psd=raw_is_psd,
        raw_symmetry_error=symmetry_error,
        corrected_min_eigenvalue=corr_min_eig,
        frobenius_distortion=frobenius_distortion,
        max_absolute_distortion=max_abs_distortion,
        relative_frobenius_distortion=rel_frobenius_distortion,
        was_correction_applied=True,
    )

    return corrected, diagnostic
