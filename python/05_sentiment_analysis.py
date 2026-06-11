"""VADER sentiment analysis on Olist reviews integrated with RFM segmentation."""

import os
import re
from pathlib import Path

import mysql.connector
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
TABLEAU_DIR = ROOT / "tableau" / "exports"


def load_env_file() -> None:
    """Load local .env values so the script can connect to MySQL without hardcoded credentials."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env_file()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "customer_retention_intelligence"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
}

COMPLAINT_THEMES = {
    "quality": ["quality", "qualidade", "defeito", "quebrado", "danificado"],
    "delivery": ["delivery", "entrega", "entregue", "atraso", "atrasado", "frete"],
    "price": ["price", "preco", "preço", "caro", "valor"],
    "expectations": ["expectations", "expectativa", "esperava", "decepcion", "decepção"],
    "service": ["service", "servico", "serviço", "atendimento", "suporte"],
}

VADER_ANALYZER = SentimentIntensityAnalyzer()


def get_mysql_connection() -> mysql.connector.MySQLConnection:
    """Open a MySQL connection using environment-driven credentials for local portability."""
    return mysql.connector.connect(**DB_CONFIG)


def load_reviews_from_mysql() -> pd.DataFrame:
    """Pull review text and star ratings from MySQL and attach customer identifiers via orders."""
    query = """
        SELECT
            r.review_id,
            r.order_id,
            r.review_score,
            r.review_comment_message,
            o.customer_id,
            o.customer_unique_id
        FROM order_reviews r
        INNER JOIN orders o
            ON r.order_id = o.order_id
    """
    connection = get_mysql_connection()
    try:
        reviews = pd.read_sql(query, connection)
    finally:
        connection.close()
    return reviews


def normalize_review_text(series: pd.Series) -> pd.Series:
    """Lowercase and strip review comments so VADER and keyword matching run on consistent text."""
    return series.fillna("").astype(str).str.strip().str.lower()


def score_vader_sentiment(reviews: pd.DataFrame) -> pd.DataFrame:
    """Compute VADER compound scores for each review comment to capture tone beyond star ratings."""
    scored = reviews.copy()
    scored["review_comment_message"] = normalize_review_text(scored["review_comment_message"])
    scored["vader_compound"] = scored["review_comment_message"].apply(
        lambda text: VADER_ANALYZER.polarity_scores(text)["compound"] if text else 0.0
    )
    return scored


def assign_hybrid_sentiment_label(compound: float, review_score: float, has_comment: bool) -> str:
    """Label reviews with VADER plus stars so high-star but negative-text reviews surface as Mixed Negative."""
    if has_comment and review_score >= 4 and compound < 0:
        return "Mixed Negative"
    if compound >= 0.05 or (not has_comment and review_score >= 4):
        return "Positive"
    if compound <= -0.05 or review_score <= 2:
        return "Negative"
    if review_score >= 4:
        return "Positive"
    return "Negative"


def apply_sentiment_labels(reviews: pd.DataFrame) -> pd.DataFrame:
    """Apply hybrid sentiment labels to every review row before customer-level aggregation."""
    labeled = reviews.copy()
    labeled["has_comment"] = labeled["review_comment_message"].str.len().gt(0)
    labeled["sentiment_label"] = labeled.apply(
        lambda row: assign_hybrid_sentiment_label(
            row["vader_compound"],
            row["review_score"],
            row["has_comment"],
        ),
        axis=1,
    )
    return labeled


def aggregate_customer_sentiment(reviews: pd.DataFrame) -> pd.DataFrame:
    """Roll review sentiment up to one customer label, prioritizing Mixed Negative as a retention risk signal."""
    customer_reviews = (
        reviews.groupby("customer_unique_id", as_index=False)
        .agg(
            customer_id=("customer_id", "first"),
            review_count=("review_id", "count"),
            avg_review_score=("review_score", "mean"),
            avg_vader_compound=("vader_compound", "mean"),
            mixed_negative_reviews=("sentiment_label", lambda s: int(s.eq("Mixed Negative").sum())),
            negative_reviews=("sentiment_label", lambda s: int(s.eq("Negative").sum())),
            positive_reviews=("sentiment_label", lambda s: int(s.eq("Positive").sum())),
        )
    )
    customer_reviews["avg_review_score"] = customer_reviews["avg_review_score"].round(2)
    customer_reviews["avg_vader_compound"] = customer_reviews["avg_vader_compound"].round(4)

    def pick_customer_label(row: pd.Series) -> str:
        if row["mixed_negative_reviews"] > 0:
            return "Mixed Negative"
        if row["negative_reviews"] >= row["positive_reviews"]:
            return "Negative"
        return "Positive"

    customer_reviews["sentiment_label"] = customer_reviews.apply(pick_customer_label, axis=1)
    return customer_reviews


def load_rfm_segmentation() -> pd.DataFrame:
    """Load the RFM export produced by segmentation.py so sentiment can be analyzed by value tier."""
    rfm_path = PROCESSED_DIR / "rfm_segmentation.csv"
    if not rfm_path.exists():
        raise FileNotFoundError(
            "rfm_segmentation.csv not found. Run segmentation.py or python/run_pipeline.py first."
        )
    return pd.read_csv(rfm_path)


def build_customer_sentiment_rfm(reviews: pd.DataFrame, rfm: pd.DataFrame) -> pd.DataFrame:
    """Join customer sentiment with RFM tiers on customer_unique_id for retention targeting."""
    customer_sentiment = aggregate_customer_sentiment(reviews)
    merged = customer_sentiment.merge(
        rfm[
            [
                "customer_unique_id",
                "value_tier",
                "recency_days",
                "frequency",
                "monetary",
                "customer_state",
            ]
        ],
        on="customer_unique_id",
        how="left",
    )
    return merged


def count_theme_mentions(text: str, keywords: list[str]) -> int:
    """Count how many theme keywords appear in a review so complaint drivers can be ranked by segment."""
    if not text:
        return 0
    return sum(len(re.findall(rf"\b{re.escape(keyword)}\b", text)) for keyword in keywords)


def extract_negative_review_themes(reviews: pd.DataFrame, rfm: pd.DataFrame) -> pd.DataFrame:
    """Count complaint-theme keyword frequency on negative reviews within each RFM segment."""
    negative_reviews = reviews[reviews["sentiment_label"].isin(["Negative", "Mixed Negative"])].copy()
    negative_reviews = negative_reviews.merge(
        rfm[["customer_unique_id", "value_tier"]],
        on="customer_unique_id",
        how="left",
    )
    negative_reviews["value_tier"] = negative_reviews["value_tier"].fillna("Unknown")

    theme_rows = []
    for value_tier, segment_reviews in negative_reviews.groupby("value_tier"):
        combined_text = " ".join(segment_reviews["review_comment_message"].tolist())
        for theme, keywords in COMPLAINT_THEMES.items():
            theme_rows.append({
                "value_tier": value_tier,
                "complaint_theme": theme,
                "mention_count": count_theme_mentions(combined_text, keywords),
                "negative_review_count": len(segment_reviews),
            })

    themes = pd.DataFrame(theme_rows)
    if themes.empty:
        return pd.DataFrame(columns=["value_tier", "complaint_theme", "mention_count", "negative_review_count"])
    return themes.sort_values(["value_tier", "mention_count"], ascending=[True, False])


def build_sentiment_distribution(customer_sentiment_rfm: pd.DataFrame) -> pd.DataFrame:
    """Summarize sentiment mix by RFM segment for Tableau distribution charts."""
    distribution = (
        customer_sentiment_rfm.groupby(["value_tier", "sentiment_label"], as_index=False)
        .agg(customers=("customer_unique_id", "nunique"))
    )
    distribution["segment_customers"] = distribution.groupby("value_tier")["customers"].transform("sum")
    distribution["sentiment_pct"] = (distribution["customers"] / distribution["segment_customers"] * 100).round(2)
    return distribution.sort_values(["value_tier", "customers"], ascending=[True, False])


def build_negative_sentiment_concentration(customer_sentiment_rfm: pd.DataFrame) -> pd.DataFrame:
    """Rank RFM segments by negative and mixed-negative concentration for prioritization dashboards."""
    concentration = (
        customer_sentiment_rfm.groupby("value_tier", as_index=False)
        .agg(
            customers=("customer_unique_id", "nunique"),
            negative_customers=("sentiment_label", lambda s: int(s.eq("Negative").sum())),
            mixed_negative_customers=("sentiment_label", lambda s: int(s.eq("Mixed Negative").sum())),
            positive_customers=("sentiment_label", lambda s: int(s.eq("Positive").sum())),
        )
    )
    concentration["negative_pct"] = (concentration["negative_customers"] / concentration["customers"] * 100).round(2)
    concentration["mixed_negative_pct"] = (
        concentration["mixed_negative_customers"] / concentration["customers"] * 100
    ).round(2)
    concentration["dissatisfied_pct"] = (
        (concentration["negative_customers"] + concentration["mixed_negative_customers"])
        / concentration["customers"]
        * 100
    ).round(2)
    return concentration.sort_values("dissatisfied_pct", ascending=False)


def export_outputs(
    customer_sentiment_rfm: pd.DataFrame,
    negative_review_themes: pd.DataFrame,
    sentiment_distribution: pd.DataFrame,
    negative_sentiment_concentration: pd.DataFrame,
) -> None:
    """Write processed analytics files and Tableau-ready sentiment exports."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)

    customer_sentiment_rfm.to_csv(PROCESSED_DIR / "customer_sentiment_rfm.csv", index=False)
    negative_review_themes.to_csv(PROCESSED_DIR / "negative_review_themes.csv", index=False)

    customer_sentiment_rfm.to_csv(TABLEAU_DIR / "tableau_customer_sentiment_rfm.csv", index=False)
    negative_review_themes.to_csv(TABLEAU_DIR / "tableau_negative_review_themes.csv", index=False)
    sentiment_distribution.to_csv(TABLEAU_DIR / "tableau_sentiment_distribution.csv", index=False)
    negative_sentiment_concentration.to_csv(TABLEAU_DIR / "tableau_negative_sentiment_concentration.csv", index=False)


def main() -> None:
    reviews = load_reviews_from_mysql()
    reviews = score_vader_sentiment(reviews)
    reviews = apply_sentiment_labels(reviews)

    rfm = load_rfm_segmentation()
    customer_sentiment_rfm = build_customer_sentiment_rfm(reviews, rfm)
    negative_review_themes = extract_negative_review_themes(reviews, rfm)
    sentiment_distribution = build_sentiment_distribution(customer_sentiment_rfm)
    negative_sentiment_concentration = build_negative_sentiment_concentration(customer_sentiment_rfm)

    export_outputs(
        customer_sentiment_rfm,
        negative_review_themes,
        sentiment_distribution,
        negative_sentiment_concentration,
    )
    print("Sentiment analysis exports created in data/processed and tableau/exports.")


if __name__ == "__main__":
    main()
