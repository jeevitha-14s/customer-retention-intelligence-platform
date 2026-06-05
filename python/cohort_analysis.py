"""Monthly cohort retention and revenue retention exports for Tableau."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
TABLEAU_DIR = ROOT / "tableau" / "exports"


def build_cohorts(orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    delivered = orders[orders["order_status"].eq("delivered")].copy()
    delivered["order_purchase_timestamp"] = pd.to_datetime(delivered["order_purchase_timestamp"])
    delivered["order_month"] = delivered["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    delivered["cohort_month"] = delivered.groupby("customer_unique_id")["order_month"].transform("min")
    delivered["months_since_first_purchase"] = (
        (delivered["order_month"].dt.year - delivered["cohort_month"].dt.year) * 12
        + (delivered["order_month"].dt.month - delivered["cohort_month"].dt.month)
    )

    cohort_counts = (
        delivered.groupby(["cohort_month", "months_since_first_purchase"], as_index=False)
        .agg(active_customers=("customer_unique_id", "nunique"), revenue=("order_revenue", "sum"))
    )
    cohort_counts["cohort_size"] = cohort_counts.groupby("cohort_month")["active_customers"].transform("first")
    cohort_counts["month_0_revenue"] = cohort_counts.groupby("cohort_month")["revenue"].transform("first")
    cohort_counts["retention_pct"] = (cohort_counts["active_customers"] / cohort_counts["cohort_size"] * 100).round(2)
    cohort_counts["revenue_retention_pct"] = (cohort_counts["revenue"] / cohort_counts["month_0_revenue"] * 100).round(2)

    retention_matrix = cohort_counts.pivot_table(
        index="cohort_month",
        columns="months_since_first_purchase",
        values="retention_pct",
        fill_value=0,
    ).reset_index()

    revenue_matrix = cohort_counts.pivot_table(
        index="cohort_month",
        columns="months_since_first_purchase",
        values="revenue_retention_pct",
        fill_value=0,
    ).reset_index()

    return cohort_counts, retention_matrix, revenue_matrix


def main() -> None:
    orders = pd.read_csv(PROCESSED_DIR / "orders_clean.csv")
    cohort_long, retention_matrix, revenue_matrix = build_cohorts(orders)

    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)
    cohort_long.to_csv(PROCESSED_DIR / "cohort_retention_long.csv", index=False)
    retention_matrix.to_csv(PROCESSED_DIR / "cohort_retention_matrix.csv", index=False)
    revenue_matrix.to_csv(PROCESSED_DIR / "cohort_revenue_retention_matrix.csv", index=False)
    cohort_long.to_csv(TABLEAU_DIR / "tableau_cohort_retention_long.csv", index=False)
    retention_matrix.to_csv(TABLEAU_DIR / "tableau_cohort_retention_matrix.csv", index=False)
    revenue_matrix.to_csv(TABLEAU_DIR / "tableau_cohort_revenue_retention_matrix.csv", index=False)
    print("Cohort analysis exports created.")


if __name__ == "__main__":
    main()
