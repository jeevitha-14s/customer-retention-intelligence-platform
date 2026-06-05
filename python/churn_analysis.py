"""Churn, CLV, and revenue-at-risk analysis exports."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
TABLEAU_DIR = ROOT / "tableau" / "exports"
CHURN_DAYS = 180


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pd.read_csv(PROCESSED_DIR / "orders_clean.csv", parse_dates=["order_purchase_timestamp"])
    customers = pd.read_csv(PROCESSED_DIR / "customers_clean.csv")
    rfm = pd.read_csv(PROCESSED_DIR / "rfm_segmentation.csv")
    return orders, customers, rfm


def build_churn_tables(orders: pd.DataFrame, customers: pd.DataFrame, rfm: pd.DataFrame) -> dict[str, pd.DataFrame]:
    delivered = orders[orders["order_status"].eq("delivered")].copy()
    analysis_date = delivered["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    customer_value = (
        delivered.groupby("customer_unique_id", as_index=False)
        .agg(
            first_purchase_date=("order_purchase_timestamp", "min"),
            last_purchase_date=("order_purchase_timestamp", "max"),
            order_count=("order_id", "nunique"),
            historical_clv=("order_revenue", "sum"),
            avg_order_value=("order_revenue", "mean"),
        )
    )
    customer_value["days_since_last_purchase"] = (analysis_date - customer_value["last_purchase_date"]).dt.days
    customer_value["is_churned"] = customer_value["days_since_last_purchase"] > CHURN_DAYS
    customer_value["customer_lifespan_days"] = (customer_value["last_purchase_date"] - customer_value["first_purchase_date"]).dt.days.clip(lower=1)
    customer_value["estimated_revenue_at_risk"] = customer_value["avg_order_value"].where(customer_value["is_churned"], 0)

    customer_churn = (
        customer_value.merge(customers[["customer_unique_id", "customer_city", "customer_state"]], on="customer_unique_id", how="left")
        .merge(rfm[["customer_unique_id", "value_tier"]], on="customer_unique_id", how="left")
    )

    churn_by_segment = (
        customer_churn.groupby("value_tier", as_index=False)
        .agg(
            customers=("customer_unique_id", "nunique"),
            churned_customers=("is_churned", "sum"),
            historical_revenue=("historical_clv", "sum"),
            revenue_at_risk=("estimated_revenue_at_risk", "sum"),
        )
    )
    churn_by_segment["churn_rate_pct"] = (churn_by_segment["churned_customers"] / churn_by_segment["customers"] * 100).round(2)

    churn_by_region = (
        customer_churn.groupby("customer_state", as_index=False)
        .agg(
            customers=("customer_unique_id", "nunique"),
            churned_customers=("is_churned", "sum"),
            historical_revenue=("historical_clv", "sum"),
            revenue_at_risk=("estimated_revenue_at_risk", "sum"),
        )
    )
    churn_by_region["churn_rate_pct"] = (churn_by_region["churned_customers"] / churn_by_region["customers"] * 100).round(2)

    month_ends = pd.DataFrame({"month": pd.date_range(delivered["order_purchase_timestamp"].min(), delivered["order_purchase_timestamp"].max(), freq="ME")})
    trend_rows = []
    for month_end in month_ends["month"]:
        eligible = customer_value[customer_value["first_purchase_date"] <= month_end].copy()
        eligible["churned_as_of_month"] = (month_end - eligible["last_purchase_date"]).dt.days > CHURN_DAYS
        trend_rows.append({
            "month": month_end.to_period("M").to_timestamp(),
            "known_customers": eligible["customer_unique_id"].nunique(),
            "churned_customers": int(eligible["churned_as_of_month"].sum()),
            "churn_rate_pct": round(eligible["churned_as_of_month"].mean() * 100, 2) if len(eligible) else 0,
        })
    churn_trend = pd.DataFrame(trend_rows)

    executive_kpis = pd.DataFrame([{
        "total_customers": customer_churn["customer_unique_id"].nunique(),
        "active_customers": int((~customer_churn["is_churned"]).sum()),
        "churned_customers": int(customer_churn["is_churned"].sum()),
        "churn_rate_pct": round(customer_churn["is_churned"].mean() * 100, 2),
        "revenue": round(delivered["order_revenue"].sum(), 2),
        "average_historical_clv": round(customer_churn["historical_clv"].mean(), 2),
        "average_customer_lifespan_days": round(customer_churn["customer_lifespan_days"].mean(), 2),
        "revenue_at_risk": round(customer_churn["estimated_revenue_at_risk"].sum(), 2),
        "churn_definition_days": CHURN_DAYS,
    }])

    return {
        "customer_churn_clv": customer_churn,
        "churn_by_segment": churn_by_segment,
        "churn_by_region": churn_by_region,
        "churn_trend": churn_trend,
        "executive_kpis": executive_kpis,
    }


def main() -> None:
    orders, customers, rfm = load_inputs()
    tables = build_churn_tables(orders, customers, rfm)
    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
        df.to_csv(TABLEAU_DIR / f"tableau_{name}.csv", index=False)
    print("Churn, CLV, and KPI exports created.")


if __name__ == "__main__":
    main()
