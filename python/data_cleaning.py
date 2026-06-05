"""Prepare normalized, analytics-ready CSV files from the raw Olist dataset."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLEAU_DIR = ROOT / "tableau" / "exports"


def clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
    )


def load_raw_data() -> dict[str, pd.DataFrame]:
    return {
        "customers": pd.read_csv(RAW_DIR / "olist_customers_dataset.csv"),
        "orders": pd.read_csv(RAW_DIR / "olist_orders_dataset.csv", parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]),
        "items": pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv", parse_dates=["shipping_limit_date"]),
        "products": pd.read_csv(RAW_DIR / "olist_products_dataset.csv"),
        "translations": pd.read_csv(RAW_DIR / "product_category_name_translation.csv", encoding="utf-8-sig"),
    }


def build_clean_tables(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    customers = raw["customers"].copy()
    orders = raw["orders"].copy()
    items = raw["items"].copy()
    products = raw["products"].copy()
    translations = raw["translations"].copy()

    customers["customer_city"] = clean_text(customers["customer_city"])
    customers["customer_state"] = customers["customer_state"].astype("string").str.upper()

    products = products.merge(translations, on="product_category_name", how="left")
    products["product_category_name"] = products["product_category_name"].fillna("unknown")
    products["product_category_english"] = products["product_category_name_english"].fillna(products["product_category_name"])
    products = products.drop(columns=["product_category_name_english"])

    delivered_orders = orders[orders["order_status"].eq("delivered")].copy()
    order_financials = (
        items.groupby("order_id", as_index=False)
        .agg(order_revenue=("price", "sum"), order_freight=("freight_value", "sum"), order_items=("order_item_id", "count"))
    )

    orders_clean = (
        orders.merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
        .merge(order_financials, on="order_id", how="left")
    )
    orders_clean["order_revenue"] = orders_clean["order_revenue"].fillna(0)
    orders_clean["order_freight"] = orders_clean["order_freight"].fillna(0)
    orders_clean["order_items"] = orders_clean["order_items"].fillna(0).astype(int)
    orders_clean["order_month"] = orders_clean["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()

    customer_dates = (
        orders_clean[orders_clean["order_status"].eq("delivered")]
        .groupby("customer_unique_id", as_index=False)
        .agg(first_seen_date=("order_purchase_timestamp", "min"), last_seen_date=("order_purchase_timestamp", "max"), total_orders=("order_id", "nunique"))
    )
    customer_locations = (
        customers.sort_values(["customer_unique_id", "customer_id"])
        .drop_duplicates("customer_unique_id")
        [["customer_unique_id", "customer_city", "customer_state"]]
    )
    customers_clean = customer_locations.merge(customer_dates, on="customer_unique_id", how="left")

    sales_fact = (
        delivered_orders[["order_id", "customer_id", "order_purchase_timestamp"]]
        .merge(customers[["customer_id", "customer_unique_id", "customer_city", "customer_state"]], on="customer_id", how="left")
        .merge(items, on="order_id", how="inner")
        .merge(products[["product_id", "product_category_english"]], on="product_id", how="left")
    )
    sales_fact["line_revenue"] = sales_fact["price"] + sales_fact["freight_value"]
    sales_fact["order_month"] = sales_fact["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()

    return {
        "customers_clean": customers_clean,
        "orders_clean": orders_clean,
        "order_items_clean": items,
        "products_clean": products,
        "sales_fact": sales_fact,
    }


def save_tables(tables: dict[str, pd.DataFrame]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)

    tables["sales_fact"].to_csv(TABLEAU_DIR / "tableau_sales_fact.csv", index=False)
    tables["orders_clean"].to_csv(TABLEAU_DIR / "tableau_orders.csv", index=False)
    tables["customers_clean"].to_csv(TABLEAU_DIR / "tableau_customers.csv", index=False)


def main() -> None:
    raw = load_raw_data()
    tables = build_clean_tables(raw)
    save_tables(tables)
    print("Clean data exports created in data/processed and tableau/exports.")


if __name__ == "__main__":
    main()
