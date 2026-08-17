CREATE OR REPLACE VIEW gold_daily_metrics AS
SELECT
    CAST(occurred_at AS DATE) AS event_date,
    COUNT(*) AS event_count,
    ROUND(AVG(magnitude), 2) AS average_magnitude,
    MAX(magnitude) AS maximum_magnitude,
    ROUND(AVG(depth_km), 2) AS average_depth_km,
    SUM(CASE WHEN tsunami THEN 1 ELSE 0 END) AS tsunami_events,
    SUM(COALESCE(felt, 0)) AS felt_reports
FROM earthquakes
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE VIEW gold_region_metrics AS
SELECT
    region,
    COUNT(*) AS event_count,
    ROUND(AVG(magnitude), 2) AS average_magnitude,
    MAX(magnitude) AS maximum_magnitude,
    MAX(depth_km) AS deepest_event_km
FROM earthquakes
GROUP BY 1
ORDER BY event_count DESC, region;

CREATE OR REPLACE VIEW gold_magnitude_distribution AS
SELECT
    magnitude_band,
    COUNT(*) AS event_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM earthquakes
GROUP BY 1
ORDER BY CASE magnitude_band
    WHEN 'micro' THEN 1
    WHEN 'minor' THEN 2
    WHEN 'light' THEN 3
    WHEN 'moderate' THEN 4
    WHEN 'strong' THEN 5
    WHEN 'major' THEN 6
    WHEN 'great' THEN 7
    ELSE 8
END;
