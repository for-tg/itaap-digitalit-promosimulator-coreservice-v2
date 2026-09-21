"""Simulation endpoints for retrospective and future planning."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.engine import promo_engine
from app.engine.promo_engine import (
    build_forecast_sku_inputs,
    compute_reference_spend,
    compute_sku_quarterly_discount_bounds,
    prepare_sku_inputs,
)
from app.schemas.requests import PlanRequest, RetroRequest
from app.services.simulation_service import (
    _actual_from_data,
    _alpha_from_request,
    _get_period_bounds,
    _quarter_budgets_from_pcts,
    _quarter_proportions_actual,
    run_common,
)


logger = logging.getLogger(__name__)

router = APIRouter()



def _resolve_market_defaults(req, plan: bool) -> None:
    """Fill request fields the caller left unset from the loaded artifact.

    These used to be Czech-era literals in the schema (year 2025, plan year
    2026, max discount 0.25). A Pydantic default is evaluated at import, before
    any pickle is loaded, so the market's own values have to be applied here.
    """
    years = promo_engine.history_years()
    last_history = max(years) if years else None

    if getattr(req, "max_discount", None) is None:
        req.max_discount = promo_engine.MAX_DISCOUNT_DEFAULT
    if getattr(req, "ref_year", None) is None and last_history:
        req.ref_year = last_history

    if plan:
        if req.plan_year is None:
            req.plan_year = (
                promo_engine.PLAN_YEAR
                if promo_engine.PLAN_YEAR
                else (last_history + 1 if last_history else None)
            )
        if req.base_year is None:
            req.base_year = last_history
    elif req.year is None:
        req.year = last_history


@router.post("/api/run_retro")
def run_retro(req: RetroRequest) -> dict:
    """Run a retrospective promotion simulation."""

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    try:
        economics = req.economics
        _resolve_market_defaults(req, plan=False)

        (start_year, start_week), (end_year, end_week) = (
            _get_period_bounds(
                req.year,
                req.period,
            )
        )

        grid_all = promo_engine.DISCOUNT_GRID_ALL
        discount_grid = grid_all[
            grid_all <= req.max_discount + 0.001
        ]

        sku_inputs = prepare_sku_inputs(
            req.skus,
            start_year,
            start_week,
            end_year=end_year,
            end_week=end_week,
            economics=economics,
        )

        if not sku_inputs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data found for the selected SKUs and period.",
            )

        discount_bounds = compute_sku_quarterly_discount_bounds(
            tuple(req.skus)
        )

        actual_results = _actual_from_data(
            sku_inputs,
            economics=economics,
        )

        actual_spend = sum(
            sku_result["promo_spend"].sum()
            for sku_result in actual_results.values()
        )

        if req.unconstrained:
            budget_cap = float("inf")
        else:
            budget_cap = max(
                actual_spend * req.budget_multiplier,
                1.0,
            )

        alpha = _alpha_from_request(
            req.alpha,
            req.objective,
        )

        quarter_budgets = None

        if not req.unconstrained:
            if (
                req.allocation_mode == "custom"
                and req.q_splits
            ):
                quarter_percentages = req.q_splits
            else:
                quarter_percentages = (
                    _quarter_proportions_actual(
                        actual_results
                    )
                )

            quarter_budgets = (
                _quarter_budgets_from_pcts(
                    budget_cap,
                    quarter_percentages,
                )
            )

        if req.period == "Full year":
            period_text = f"Full year {req.year}"
        else:
            period_text = f"{req.period} {req.year}"

        return run_common(
            sku_inputs=sku_inputs,
            actual_results=actual_results,
            budget_cap=budget_cap,
            disc_grid=discount_grid,
            alpha=alpha,
            discount_bounds=discount_bounds,
            period_label=(
                f"Recommendation · {period_text} · "
                f"{promo_engine.PORTFOLIO_LABEL}"
            ),
            margin_floor=req.margin_floor,
            quarter_budgets=quarter_budgets,
            economics=economics,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Unexpected error while running retrospective simulation."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete the retrospective simulation.",
        ) from exc


@router.post("/api/run_plan")
def run_plan(req: PlanRequest) -> dict:
    """Run a future promotion planning simulation."""

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    try:
        economics = req.economics
        _resolve_market_defaults(req, plan=True)

        grid_all = promo_engine.DISCOUNT_GRID_ALL
        discount_grid = grid_all[
            grid_all <= req.max_discount + 0.001
        ]

        sku_inputs = build_forecast_sku_inputs(
            req.skus,
            base_year=req.base_year,
            use_trend=req.use_trend,
            economics=economics,
        )

        if not sku_inputs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data found for the selected SKUs.",
            )

        reference_spend = compute_reference_spend(
            tuple(req.skus),
            req.ref_year,
            economics=economics,
        )

        if req.unconstrained:
            budget_cap = float("inf")
        else:
            budget_cap = max(
                reference_spend * req.budget_multiplier,
                1.0,
            )

        discount_bounds = compute_sku_quarterly_discount_bounds(
            tuple(req.skus)
        )

        alpha = _alpha_from_request(
            req.alpha,
            req.objective,
        )

        if req.unconstrained:
            quarter_budgets = None
        else:
            quarter_budgets = (
                _quarter_budgets_from_pcts(
                    budget_cap,
                    req.q_splits,
                )
            )

        historical_results = None

        try:
            reference_sku_inputs = prepare_sku_inputs(
                req.skus,
                req.ref_year,
                1,
                end_year=req.ref_year,
                end_week=promo_engine.WEEKS_PER_YEAR,
                economics=economics,
            )

            if reference_sku_inputs:
                historical_results = (
                    _actual_from_data(
                        reference_sku_inputs,
                        economics=economics,
                    )
                )

        except Exception:
            logger.warning(
                "Historical comparison data could not be prepared.",
                exc_info=True,
            )

        return run_common(
            sku_inputs=sku_inputs,
            actual_results={},
            budget_cap=budget_cap,
            disc_grid=discount_grid,
            alpha=alpha,
            discount_bounds=discount_bounds,
            period_label=(
                f"Plan · {req.plan_year} · "
                f"{promo_engine.PORTFOLIO_LABEL}"
            ),
            compare_vs_base=True,
            hist_results=historical_results,
            hist_year=req.ref_year,
            margin_floor=req.margin_floor,
            quarter_budgets=quarter_budgets,
            economics=economics,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Unexpected error while running planning simulation."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete the planning simulation.",
        ) from exc