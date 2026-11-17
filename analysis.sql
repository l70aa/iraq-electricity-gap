CREATE VIEW governorate_metrics AS
WITH pop AS (
  SELECT governorate, year, SUM(population) AS population
  FROM population
  GROUP BY governorate, year
)
SELECT p.governorate, p.year, p.population, e.demand_mw, e.supplied_mw,
       e.demand_mw - e.supplied_mw AS gap_mw,
       ROUND(100.0 * e.supplied_mw / NULLIF(e.demand_mw, 0), 2) AS coverage_pct,
       ROUND(100000.0 * (e.demand_mw - e.supplied_mw) / p.population, 2) AS gap_mw_per_100k,
       CASE WHEN e.governorate IS NULL THEN 'Not yet verified' ELSE 'Matched' END AS status,
       e.source_url
FROM pop AS p
LEFT JOIN electricity AS e USING (governorate, year);

CREATE VIEW matched_scope AS
SELECT year, COUNT(*) AS matched_governorates, SUM(population) AS matched_population,
       SUM(demand_mw) AS demand_mw, SUM(supplied_mw) AS supplied_mw,
       SUM(gap_mw) AS gap_mw,
       ROUND(100.0 * SUM(supplied_mw) / SUM(demand_mw), 2) AS coverage_pct
FROM governorate_metrics
WHERE status = 'Matched'
GROUP BY year;

-- The 2025 source is available here as an aggregate for the fixed common scope.
CREATE VIEW comparable_grid AS
WITH totals AS (
  SELECT year, COUNT(*) AS governorate_count,
         SUM(demand_mw) AS demand_mw, SUM(supplied_mw) AS supplied_mw
  FROM electricity
  WHERE governorate NOT IN ('Baghdad', 'Anbar')
  GROUP BY year
  UNION ALL
  SELECT year, governorate_count, demand_mw, supplied_mw FROM power_common_scope
)
SELECT *, demand_mw - supplied_mw AS gap_mw,
       1.0 * supplied_mw / demand_mw AS coverage
FROM totals;

CREATE VIEW grid_delta AS
SELECT b.demand_mw - a.demand_mw AS demand_delta,
       b.supplied_mw - a.supplied_mw AS supply_delta,
       b.gap_mw - a.gap_mw AS gap_delta,
       100 * (b.coverage - a.coverage) AS coverage_delta_pp
FROM comparable_grid AS a CROSS JOIN comparable_grid AS b
WHERE a.year = 2024 AND b.year = 2025
  AND a.governorate_count = b.governorate_count;

CREATE VIEW grid_target AS
WITH targets(target_pct) AS (VALUES (60), (70), (80)),
     growth(growth_pct) AS (VALUES (0), (5), (10)),
     estimates AS (
       SELECT target_pct, growth_pct, supplied_mw,
              demand_mw * (100 + growth_pct) * target_pct AS scaled_target_mw
       FROM comparable_grid CROSS JOIN targets CROSS JOIN growth WHERE year = 2025
     )
SELECT target_pct, growth_pct,
       (scaled_target_mw + 9999) / 10000 AS required_supply_mw,
       MAX(0, (scaled_target_mw + 9999) / 10000 - supplied_mw) AS additional_supply_mw
FROM estimates;
