"""
services/mlflow_service.py
--------------------------
MLflow experiment tracking for LLM inference.

What this tracks:
  - Every LLM call is logged as an MLflow run inside the "llm-saas-backend" experiment.
  - Parameters logged: model name, prompt length, tenant_id, user_id
  - Metrics logged: response length, latency in milliseconds
  - Tags: mock mode flag, environment

Why this matters for MLOps:
  - Gives you a full audit trail of every inference
  - Lets you compare latency across model versions
  - Enables drift detection (prompt/response length over time)
  - Foundation for A/B testing different LLM providers

View the MLflow UI:
  mlflow ui --port 5001
  Then open: http://localhost:5001
"""

import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# MLflow experiment name — all runs are grouped under this
EXPERIMENT_NAME = "llm-saas-backend"


def _get_mlflow():
    """
    Lazy import mlflow so the app still starts if mlflow isn't installed.
    Returns the mlflow module or None.
    """
    try:
        import mlflow
        return mlflow
    except ImportError:
        logger.warning("mlflow not installed — tracking disabled. Run: pip install mlflow")
        return None


def setup_mlflow() -> None:
    """
    Called once at application startup.
    Creates the experiment if it doesn't exist.
    Uses local file storage by default (./mlruns folder).
    In production, point MLFLOW_TRACKING_URI to a remote server.
    """
    mlflow = _get_mlflow()
    if mlflow is None:
        return

    tracking_uri = getattr(settings, "MLFLOW_TRACKING_URI", "mlruns")
    mlflow.set_tracking_uri(tracking_uri)

    # Create experiment if it doesn't exist
    if mlflow.get_experiment_by_name(EXPERIMENT_NAME) is None:
        mlflow.create_experiment(EXPERIMENT_NAME)
        logger.info("MLflow experiment created", experiment=EXPERIMENT_NAME)

    mlflow.set_experiment(EXPERIMENT_NAME)
    logger.info("MLflow tracking initialised", uri=tracking_uri)


def track_llm_call(
    prompt: str,
    response: str,
    latency_ms: float,
    tenant_id: str,
    user_id: str,
    mock: bool = True,
) -> Optional[str]:
    """
    Log a single LLM inference as an MLflow run.

    Args:
        prompt:      The user's input prompt.
        response:    The LLM's output response.
        latency_ms:  End-to-end latency in milliseconds.
        tenant_id:   Which tenant made the request (for multi-tenant analysis).
        user_id:     Which user made the request.
        mock:        Whether the mock LLM was used.

    Returns:
        The MLflow run_id string, or None if tracking failed.
    """
    mlflow = _get_mlflow()
    if mlflow is None:
        return None

    try:
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run() as run:
            # ── Parameters (inputs, don't change within a run) ────────────────
            mlflow.log_params({
                "model":         settings.LLM_MODEL if not mock else "mock",
                "prompt_length": len(prompt),
                "tenant_id":     tenant_id,
                "user_id":       user_id,
                "mock_mode":     mock,
                "environment":   settings.APP_ENV,
            })

            # ── Metrics (numeric, can be tracked over time) ───────────────────
            mlflow.log_metrics({
                "latency_ms":       latency_ms,
                "response_length":  len(response),
                "prompt_length":    float(len(prompt)),
                # Tokens are approximated at ~4 chars per token
                "approx_tokens_in":  len(prompt) / 4,
                "approx_tokens_out": len(response) / 4,
            })

            # ── Tags (searchable labels) ──────────────────────────────────────
            mlflow.set_tags({
                "tenant_id":   tenant_id,
                "source":      "api",
            })

            run_id = run.info.run_id
            logger.info("MLflow run logged", run_id=run_id, latency_ms=latency_ms)
            return run_id

    except Exception as exc:
        # Never let tracking failures break the main request
        logger.warning("MLflow tracking failed (non-fatal)", error=str(exc))
        return None
