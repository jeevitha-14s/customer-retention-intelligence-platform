"""Customer segmentation using RFM scoring and value tiers."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
TABLEAU_DIR = ROOT / "tableau" / "exports"


def score_rfm(orders: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    delivered = orders[orders["order_status"].eq("delivered")].copy()
    delivered["order_purchase_timestamp"] = pd.to_datetime(delivered["order_purchase_timestamp"])
    analysis_date = delivered["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    rfm = (
        delivered.groupby("customer_unique_id", as_index=False)
        .agg(
            last_purchase_date=("order_purchase_timestamp", "max"),
            first_purchase_date=("order_purchase_timestamp", "min"),
            frequency=("order_id", "nunique"),
            monetary=("order_revenue", "sum"),
            avg_order_value=("order_revenue", "mean"),
        )
    )
    rfm["recency_days"] = (analysis_date - rfm["last_purchase_date"]).dt.days
    rfm["customer_lifespan_days"] = (rfm["last_purchase_date"] - rfm["first_purchase_date"]).dt.days.clip(lower=1)

    rfm["recency_score"] = pd.qcut(rfm["recency_days"].rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["frequency_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["monetary_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["rfm_score"] = rfm["recency_score"] + rfm["frequency_score"] + rfm["monetary_score"]

    conditions = [
        (rfm["recency_score"] >= 4) & (rfm["frequency_score"] >= 4) & (rfm["monetary_score"] >= 4),
        (rfm["recency_score"] >= 3) & (rfm["frequency_score"] >= 3),
        (rfm["recency_score"] <= 2) & (rfm["monetary_score"] >= 3),
        (rfm["recency_score"] <= 2),
    ]
    tiers = ["VIP", "Loyal", "At Risk", "Lost"]
    rfm["value_tier"] = np.select(conditions, tiers, default="Developing")

    return rfm.merge(customers[["customer_unique_id", "customer_city", "customer_state"]], on="customer_unique_id", how="left")


def main() -> None:
    orders = pd.read_csv(PROCESSED_DIR / "orders_clean.csv")
    customers = pd.read_csv(PROCESSED_DIR / "customers_clean.csv")
    rfm = score_rfm(orders, customers)

    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)
    rfm.to_csv(PROCESSED_DIR / "rfm_segmentation.csv", index=False)
    rfm.to_csv(TABLEAU_DIR / "tableau_rfm_segmentation.csv", index=False)

    summary = (
        rfm.groupby("value_tier", as_index=False)
        .agg(customers=("customer_unique_id", "nunique"), revenue=("monetary", "sum"), avg_clv=("monetary", "mean"), avg_recency_days=("recency_days", "mean"))
        .sort_values("revenue", ascending=False)
    )
    summary.to_csv(TABLEAU_DIR / "tableau_segment_summary.csv", index=False)
    print("RFM segmentation exports created.")


if __name__ == "__main__":
    main()
