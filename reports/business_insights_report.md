# Customer Retention Intelligence Platform: Business Insights Report

## Executive Summary

This project analyzes customer retention, churn, customer lifetime value, and revenue impact for an ecommerce business using the Olist dataset. The platform uses Python and Pandas for data preparation, MySQL for normalized analytics modeling and SQL analysis, and Tableau-ready exports for executive BI dashboards.

The analysis uses a 180-day no-purchase churn definition. Under that rule, the business has 93,358 delivered-order customers, 38,106 active customers, 55,252 churned customers, and a 59.18% churn rate. Historical delivered revenue is 13.22M, average historical CLV is 141.62, and estimated revenue at risk is 7.51M.

## Key Findings

1. Retention is the central business challenge. Only 2.10% of delivered-order customers returned within 90 days of a previous purchase, which suggests the business behaves more like a transactional marketplace than a recurring customer engine.

2. Churned and at-risk customers carry meaningful revenue. The At Risk tier generated 4.71M in historical revenue, while Lost customers generated 615K. Reactivation campaigns should focus first on high-monetary At Risk customers.

3. VIP customers are small but valuable. VIP customers represent 6,512 customers and 1.78M in historical revenue, with an average CLV of 273.99, almost double the overall average historical CLV.

4. Region matters. Sao Paulo (SP) has the strongest retention among large states, with a 44.09% active retention rate under the 180-day rule. Higher-churn regions include RO, MA, SE, AL, and PA among states with at least 100 customers.

5. Monthly cohort retention is low. Even the stronger month-one cohorts retain below 1% in the following month, which points to limited repeat purchase behavior and an opportunity to create lifecycle programs immediately after first purchase.

## Recommendations

1. Launch a first-90-days retention program. Use automated email, coupon, and category recommendation campaigns for customers after their first order, especially between day 14 and day 60.

2. Prioritize high-value At Risk customers. Build Tableau filters for customers with high monetary value and recency over 180 days, then target them with win-back offers.

3. Protect VIP customers. Give VIP customers early access, free shipping thresholds, loyalty rewards, or support prioritization to avoid losing high-CLV accounts.

4. Localize regional retention campaigns. Use SP as a benchmark region, then compare category mix, delivery time, and offer strategy against higher-churn states.

5. Improve post-purchase cross-sell. Since most customers purchase once, recommend complementary categories after delivery confirmation instead of waiting for organic repeat visits.

## Revenue Opportunities

- Revenue at risk from churned customers is estimated at 7.51M.
- At Risk customers represent 4.58M of estimated revenue at risk.
- VIP customers have the highest average CLV and should be monitored with retention alerts.
- Segment-level targeting can reduce discount waste by reserving aggressive offers for At Risk and Lost high-value customers.

## Retention Improvement Strategy

The recommended operating model is a three-part BI workflow:

1. Monitor executive KPIs weekly: total customers, active customers, churn rate, revenue, CLV, and revenue at risk.
2. Review cohort heatmaps monthly to identify whether new customers are improving in month-one and month-two retention.
3. Run segment-level action lists from RFM data for VIP protection, Loyal upsell, At Risk reactivation, and Lost win-back campaigns.
