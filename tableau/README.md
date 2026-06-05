# Tableau Dashboard Build Guide

Use the CSV files in `tableau/exports/` as Tableau data sources. The project is designed so each dashboard can be built without writing custom Tableau SQL.

## Data Sources

- `tableau_sales_fact.csv`: line-level order item sales with customer, region, product category, revenue, and order month.
- `tableau_orders.csv`: order-level fact table with order revenue and delivery status.
- `tableau_customers.csv`: customer dimension with city, state, first purchase, and last purchase.
- `tableau_rfm_segmentation.csv`: customer RFM scores and value tiers.
- `tableau_segment_summary.csv`: segment-level revenue and CLV summary.
- `tableau_cohort_retention_long.csv`: cohort month, months since first purchase, retention, and revenue retention.
- `tableau_churn_by_segment.csv`: churn rate and revenue at risk by value tier.
- `tableau_churn_by_region.csv`: churn rate and revenue at risk by state.
- `tableau_churn_trend.csv`: monthly churn trend.
- `tableau_executive_kpis.csv`: headline KPI values.

## Dashboard 1: Executive Overview

Recommended sheets:

- KPI cards: Total Customers, Active Customers, Churn Rate, Revenue, Average Historical CLV.
- Monthly revenue line chart using `tableau_orders.csv`.
- Revenue by state map using `tableau_sales_fact.csv`.
- Customer distribution by value tier using `tableau_segment_summary.csv`.

## Dashboard 2: Retention Dashboard

Recommended sheets:

- Cohort heatmap: rows = `cohort_month`, columns = `months_since_first_purchase`, color = `retention_pct`.
- Revenue retention heatmap: same layout, color = `revenue_retention_pct`.
- Returning customer trend by order month from `tableau_orders.csv`.

## Dashboard 3: Churn Dashboard

Recommended sheets:

- Churn by segment bar chart using `tableau_churn_by_segment.csv`.
- Churn by region map using `tableau_churn_by_region.csv`.
- Churn trend line using `tableau_churn_trend.csv`.
- Revenue at risk by segment.

## Dashboard 4: Customer Segmentation Dashboard

Recommended sheets:

- RFM scatter plot: frequency vs monetary, color by `value_tier`.
- VIP customer table sorted by monetary value.
- Customer distribution by tier.
- Average recency by tier.

## Dashboard 5: Revenue Impact Dashboard

Recommended sheets:

- Revenue at risk KPI.
- CLV by segment.
- Revenue retention cohort heatmap.
- Historical revenue from churned customers by state.

## Screenshot Placeholder

After building the workbook, export dashboard images into `dashboard_screenshots/` with these suggested names:

- `executive_overview.png`
- `retention_dashboard.png`
- `churn_dashboard.png`
- `segmentation_dashboard.png`
- `revenue_impact_dashboard.png`
