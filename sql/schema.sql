CREATE TABLE IF NOT EXISTS earthquakes (
    event_id VARCHAR PRIMARY KEY,
    magnitude DOUBLE,
    magnitude_band VARCHAR NOT NULL,
    place VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    longitude DOUBLE NOT NULL,
    latitude DOUBLE NOT NULL,
    depth_km DOUBLE NOT NULL,
    event_type VARCHAR NOT NULL,
    alert VARCHAR,
    tsunami BOOLEAN NOT NULL,
    felt INTEGER,
    significance INTEGER,
    detail_url VARCHAR,
    source_net VARCHAR,
    status VARCHAR,
    ingested_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    feed VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    extracted_count INTEGER DEFAULT 0,
    accepted_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    status VARCHAR NOT NULL,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS quality_results (
    run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    passed BOOLEAN NOT NULL,
    observed_value VARCHAR,
    expectation VARCHAR NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL
);
