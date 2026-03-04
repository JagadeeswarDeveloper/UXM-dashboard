# Dashboard Feature Proposals: UXM & ESG

This document outlines the recommended features, KPIs, and data mappings for the upcoming UXM and ESG dashboards.

---

## 1. UXM Dashboard (User Experience Management)
*Focus: Measuring employee satisfaction, productivity loss, and IT service quality.*

### Key Features
| Feature Name | Visualization Type | Description | Data Column(s) |
| :--- | :--- | :--- | :--- |
| **Global Happiness Index** | Gauge / Big Number | Real-time average of user satisfaction scores. | `happiness_score` |
| **Productivity Impact** | Trend Line / Counter | Total hours lost due to IT issues (converted from minutes). | `lost_time_minutes` |
| **Burnout Risk Heatmap** | Matrix Chart | Identifies departments or regions with high burnout risk levels. | `burnout_risk_score`, `department` |
| **Sentiment Analysis** | Word Cloud / Feed | Common themes from open-text user feedback. | `factors`, `comment` |
| **Channel Performance** | Bar Chart | Comparison of satisfaction between "Self-Service", "Email", and "Phone". | `channel`, `happiness_score` |
| **Regional Leaderboard**| Map / Ranked List | Highlighting locations with the best/worst IT experience. | `country`, `region` |

---

## 2. ESG Dashboard (Environmental, Social, Governance)
*Focus: IT sustainability, carbon footprint, and energy efficiency.*

### Key Features
| Feature Name | Visualization Type | Description | Data Column(s) |
| :--- | :--- | :--- | :--- |
| **Fleet Eco-Score** | Donut Chart | Distribution of EPEAT ratings (Gold vs. Silver vs. Bronze). | `epeat_rating` |
| **Carbon Footprint** | Big Number | Total CO2 emissions (Kg) from manufacturing and usage. | `lifecycle_kg_co2`, `co2_emissions_kg` |
| **Energy Efficiency** | Histogram | Distribution of energy consumption across the device fleet. | `energy_consumption_kwh` |
| **Manufacturer "Green" Rank**| Ranked List | Comparing sustainability metrics across different vendors. | `material_composition` (JSON) |
| **Power Intensity** | Scatter Plot | Relationship between CPU power rating and actual efficiency. | `cpu_power_rating`, `energy_star_rating` |
| **Asset Lifecycle** | Stacked Bar | Breakdown of Manufacturing vs. Operational carbon impact. | `manufacturing_kg_co2`, `lifecycle_kg_co2` |

---

## 3. Advanced Dashboard Capabilities
- **Time-Drilldown**: Both dashboards should allow filtering by `load_date` or `created_date` to see monthly/quarterly trends (e.g., "Is our productivity loss decreasing?").
- **Cross-Filtering**: Selecting a "Department" on the UXM dashboard could filter the ESG dashboard to see the environmental impact of that specific group's hardware.
- **Audit Transparency**: A small "Data Freshness" indicator in the footer showing the last successful ingestion from `load_audit`.

---

## 4. UI Developer Roadmap
1.  **Direct Mapping**: Map the widgets above directly to the `RAW_HAPPYSIGNALS_SURVEYS` and `RAW_ESG_METRICS` tables.
2.  **Aggregation**: Use SQL `AVG()`, `SUM()`, and `COUNT()` group by `Department`, `Country`, or `EPEAT_Rating`.
3.  **JSON Handling**: For Manufacturer information, the UI or backend will need to parse the `material_composition` string.
