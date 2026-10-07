---
template_id: "25"
phase: 4
assigned_role: "data_ai/data_analyst"
context_from: ["product_design/03_requirements_engineering.md", "engineering/04_system_design_architecture.md"]
outputs_to: ["engineering/05_technical_sdlc_execution.md"]
status: template
---
# Template 25: Data Analytics & SQL Dashboard Specification

**Purpose:** To define core business metrics, SQL aggregation schemas, event telemetry schemas, visualization widgets, and reporting data pipelines for client dashboards.

---

## 1. Business Metrics & KPI Dictionary

| Metric Name | Calculation / Formula | Business Meaning | Target / SLA |
| :--- | :--- | :--- | :--- |
| **Monthly Recurring Revenue (MRR)** | `SUM(active_subscriptions.monthly_amount)` | Predictable monthly software revenue | `Growth > 10% MoM` |
| **Daily Active Users (DAU)** | `COUNT(DISTINCT user_id WHERE last_active >= NOW() - INTERVAL '1 day')` | Daily user engagement depth | `DAU/MAU > 25%` |
| **User Churn Rate** | `(canceled_users_in_period / total_users_start_period) * 100` | Percentage of subscribers lost | `< 2.5% / month` |
| **Average Order Value (AOV)** | `SUM(order_total) / COUNT(orders)` | Average revenue generated per transaction | `> $75.00` |

## 2. Event Telemetry & Tracking Schema
Specify the client-side and server-side tracking events required:

```json
{
  "event_name": "button_clicked",
  "properties": {
    "button_id": "cta_checkout_start",
    "page_location": "/pricing",
    "plan_selected": "enterprise_annual",
    "user_id": "usr_948271",
    "session_id": "ses_381029",
    "timestamp": "2026-08-30T11:00:00Z"
  }
}
```

## 3. SQL Aggregation Queries & Materialized Views

```sql
-- Materialized View: Daily Executive KPI Snapshot
CREATE MATERIALIZED VIEW mv_daily_executive_metrics AS
SELECT
    DATE_TRUNC('day', o.created_at) AS report_date,
    COUNT(DISTINCT o.user_id) AS active_transacting_users,
    COUNT(o.id) AS total_orders,
    SUM(o.amount_cents) / 100.0 AS total_revenue_usd,
    AVG(o.amount_cents) / 100.0 AS average_order_value_usd
FROM orders o
WHERE o.status = 'completed'
GROUP BY DATE_TRUNC('day', o.created_at)
ORDER BY report_date DESC;

-- Refresh strategy: Executed every hour via pg_cron or serverless cron
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_executive_metrics;
```

## 4. Dashboard Layout & Widget Breakdown

| Widget ID | Visual Type | Data Source / View | Default Date Range | Refresh Frequency |
| :--- | :--- | :--- | :--- | :--- |
| `WIDGET-01` | Big Number Card | `mv_daily_executive_metrics` (Today's MRR) | Current Month | Hourly |
| `WIDGET-02` | Line Chart | 30-Day Revenue Trend vs Prior Month | Last 30 Days | Hourly |
| `WIDGET-03` | Donut Chart | Revenue by Plan Tier (Starter, Pro, Enterprise) | All Time Active | Daily |
| `WIDGET-04` | Data Table | Top 25 Highest Value Accounts (with Search/Filter) | Real-time | Real-time query |

## 5. Data Privacy & Retention Policy
- **Anonymization:** User IP addresses hashed with salt after 30 days.
- **Retention Period:** Raw event logs retained in hot storage for 90 days; rolled up into daily aggregates for 3 years.
- **Access Control:** Dashboard restricted by role-based access control (RBAC: `Admin` and `Executive` roles only).

---

## ✍️ Human Lead Decision & Sign-Off Block
*(Strictly used to gate progress and record architectural/business decisions)*

**Reviewed By:** `[Human Lead Name]`
**Date:** `[YYYY-MM-DD]`

* **Key Decision 1 (KPI Definitions):** `[Agreement on exact SQL calculation formulas for core metrics]`
* **Key Decision 2 (Performance & Views):** `[Materialized view refresh frequency and indexing strategy]`
* **Key Decision 3 (Data Privacy):** `[Retention window and PII masking guidelines]`

### Decision (Select One):
1. [ ] **Approved:** Proceed to the next phase / merge the PR.
2. [ ] **Approved with Minor Revisions:** Proceed, but resolve the inline comments before final handoff.
3. [ ] **Rejected (Requires Rework):** Blocked. The agent/developer must address the critical flaws noted below and resubmit.

**Lead Notes / Specific Overrides:**
* `[Type 'Approved' or enter adjustments]`

**Status:** ⏳ Awaiting Approval

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] SQL aggregation queries tested on sample database and validated for index efficiency.
- [ ] Event telemetry schemas documented in tracking dictionary.
- [ ] No placeholder blocks (`[TBD]`) remaining.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] `data_ai/25_data_analytics_dashboard.md`