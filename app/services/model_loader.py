"""
Model loader service.

Downloads the pickle from S3 or loads it locally, validates the
model artifact, loads optional COGS overrides, and initializes
the promo engine.
"""

import logging
import os
import pickle
import tempfile
from typing import Any

import pandas as pd

from app.config.settings import settings
from app.engine import promo_engine

logger = logging.getLogger(__name__)


_REQUIRED_MODEL_KEYS = {
    "panel_df",
    "glc_pe",
    "model",
    "feature_names",
    "confounder_names",
}


def _create_s3_client() -> Any:
    """Create and return the S3 client."""

    # Imported here so boto3 is only required when S3 loading is used.
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
    )


def _get_s3_model_key(s3_client: Any) -> str:
    """
    Return the configured S3 model key.

    If S3_MODEL_KEY is empty, find the latest pickle file under
    S3_MODEL_PREFIX.
    """

    if settings.S3_MODEL_KEY:
        return settings.S3_MODEL_KEY

    if not settings.S3_MODEL_PREFIX:
        raise ValueError(
            "S3_MODEL_KEY or S3_MODEL_PREFIX must be configured "
            "when MODEL_SOURCE is set to 's3'."
        )

    logger.info(
        "Searching for pickle files under s3://%s/%s",
        settings.S3_BUCKET_NAME,
        settings.S3_MODEL_PREFIX,
    )

    paginator = s3_client.get_paginator("list_objects_v2")

    pickle_objects: list[dict[str, Any]] = []

    for page in paginator.paginate(
        Bucket=settings.S3_BUCKET_NAME,
        Prefix=settings.S3_MODEL_PREFIX,
    ):
        for s3_object in page.get("Contents", []):
            object_key = str(s3_object.get("Key", ""))

            if object_key.lower().endswith(
                (".pkl", ".pickle")
            ):
                pickle_objects.append(s3_object)

    if not pickle_objects:
        raise FileNotFoundError(
            "No pickle file was found under "
            f"s3://{settings.S3_BUCKET_NAME}/"
            f"{settings.S3_MODEL_PREFIX}"
        )

    latest_object = max(
        pickle_objects,
        key=lambda item: item["LastModified"],
    )

    latest_key = str(latest_object["Key"])

    logger.info(
        "Selected latest model artifact: s3://%s/%s",
        settings.S3_BUCKET_NAME,
        latest_key,
    )

    return latest_key


def _load_pickle_from_s3() -> dict[str, Any]:
    """Download and load the model artifact from S3."""

    if not settings.S3_BUCKET_NAME:
        raise ValueError(
            "S3_BUCKET_NAME is not configured."
        )

    s3_client = _create_s3_client()
    model_key = _get_s3_model_key(s3_client)

    with tempfile.NamedTemporaryFile(
        suffix=".pkl",
        delete=False,
    ) as temporary_file:
        temporary_path = temporary_file.name

    try:
        logger.info(
            "Downloading model artifact from s3://%s/%s",
            settings.S3_BUCKET_NAME,
            model_key,
        )

        s3_client.download_file(
            settings.S3_BUCKET_NAME,
            model_key,
            temporary_path,
        )

        with open(temporary_path, "rb") as model_file:
            data = pickle.load(model_file)

        return data

    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _load_pickle_local() -> dict[str, Any]:
    """Load the model artifact from the configured local path."""

    model_path = settings.LOCAL_MODEL_PATH

    if not model_path:
        raise ValueError(
            "LOCAL_MODEL_PATH is not configured."
        )

    if not os.path.isfile(model_path):
        raise FileNotFoundError(
            f"Model artifact was not found at: {model_path}"
        )

    logger.info(
        "Loading model artifact from local path: %s",
        model_path,
    )

    with open(model_path, "rb") as model_file:
        return pickle.load(model_file)


def _validate_model_data(
    data: object,
) -> dict[str, Any]:
    """Validate the loaded model artifact structure."""

    if not isinstance(data, dict):
        raise ValueError(
            "Invalid model artifact: expected a dictionary."
        )

    missing_keys = _REQUIRED_MODEL_KEYS - set(data.keys())

    if missing_keys:
        missing_keys_text = ", ".join(
            sorted(missing_keys)
        )

        raise ValueError(
            "Invalid model artifact. "
            f"Missing required keys: {missing_keys_text}"
        )

    if not isinstance(
        data["panel_df"],
        pd.DataFrame,
    ):
        raise ValueError(
            "Invalid model artifact: "
            "panel_df must be a pandas DataFrame."
        )

    if not isinstance(
        data["glc_pe"],
        pd.DataFrame,
    ):
        raise ValueError(
            "Invalid model artifact: "
            "glc_pe must be a pandas DataFrame."
        )

    if data["panel_df"].empty:
        raise ValueError(
            "Invalid model artifact: panel_df is empty."
        )

    required_panel_columns = {
        "SKU",
        "Year",
        "Week",
    }

    missing_panel_columns = (
        required_panel_columns
        - set(data["panel_df"].columns)
    )

    if missing_panel_columns:
        missing_columns_text = ", ".join(
            sorted(missing_panel_columns)
        )

        raise ValueError(
            "Invalid panel_df. "
            f"Missing required columns: {missing_columns_text}"
        )

    return data


def _load_cogs_override() -> dict[str, float]:
    """Load optional SKU-level COGS overrides from CSV."""

    cogs_path = settings.COGS_CSV_PATH

    if not cogs_path:
        logger.info(
            "COGS override path is not configured."
        )
        return {}

    if not os.path.isfile(cogs_path):
        logger.info(
            "COGS override file was not found at %s. "
            "Continuing without overrides.",
            cogs_path,
        )
        return {}

    try:
        cogs_df = pd.read_csv(
            cogs_path,
            encoding="utf-8-sig",
        )

        required_columns = {
            "SKU",
            "COGS",
        }

        missing_columns = (
            required_columns - set(cogs_df.columns)
        )

        if missing_columns:
            missing_columns_text = ", ".join(
                sorted(missing_columns)
            )

            logger.warning(
                "Ignoring COGS override file %s because it is "
                "missing required columns: %s",
                cogs_path,
                missing_columns_text,
            )

            return {}

        cogs_df = cogs_df.dropna(
            subset=["SKU", "COGS"],
        )

        return {
            str(sku): float(cogs)
            for sku, cogs in zip(
                cogs_df["SKU"],
                cogs_df["COGS"],
            )
        }

    except (
        OSError,
        ValueError,
        TypeError,
        pd.errors.ParserError,
    ) as exc:
        logger.warning(
            "Could not load COGS override from %s: %s",
            cogs_path,
            exc,
        )

        return {}


def _validate_model_source() -> str:
    """Validate and return the configured model source."""

    model_source = (
        settings.MODEL_SOURCE.strip().lower()
    )

    supported_sources = {
        "local",
        "s3",
    }

    if model_source not in supported_sources:
        raise ValueError(
            "Unsupported MODEL_SOURCE: "
            f"{settings.MODEL_SOURCE}. "
            "Supported values are 'local' and 's3'."
        )

    app_environment = (
        settings.APP_ENV.strip().lower()
    )

    local_environments = {
        "local",
        "development",
        "dev-local",
        "build",
        "test",
    }

    if (
        model_source == "local"
        and app_environment not in local_environments
    ):
        raise RuntimeError(
            "Local model loading is not allowed for "
            f"APP_ENV='{settings.APP_ENV}'. "
            "Set MODEL_SOURCE=s3 for deployed environments."
        )

    return model_source


def load_model() -> None:
    """Load model data and initialize the promo engine once."""

    if promo_engine.is_ready():
        logger.info(
            "Promo engine is already initialized. "
            "Skipping model loading."
        )
        return

    try:
        model_source = _validate_model_source()

        logger.info(
            "Loading model artifact using source: %s",
            model_source,
        )

        if model_source == "s3":
            model_data = _load_pickle_from_s3()
        else:
            model_data = _load_pickle_local()

        validated_model_data = _validate_model_data(
            model_data
        )

        cogs_override = _load_cogs_override()

        promo_engine.init_engine(
            validated_model_data,
            cogs_override,
        )

        if not promo_engine.is_ready():
            raise RuntimeError(
                "Promo engine initialization completed, "
                "but the engine is not ready."
            )

        logger.info(
            "Promo engine initialized successfully: "
            "%s SKUs, panel shape %s",
            int(
                promo_engine.panel_df[
                    "SKU"
                ].nunique()
            ),
            promo_engine.panel_df.shape,
        )

    except Exception:
        logger.exception(
            "Failed to load the model artifact and "
            "initialize the promo engine."
        )
        raise