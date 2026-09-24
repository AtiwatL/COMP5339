-- COMP5339 Assignment 1: normalized spatial EV charger schema
-- DuckDB 1.5+ with the spatial extension loaded is required.


CREATE TABLE sa4_region (
    sa4_code       VARCHAR PRIMARY KEY,
    sa4_name       VARCHAR NOT NULL,
    gcc_code       VARCHAR,
    gcc_name       VARCHAR,
    state_name     VARCHAR NOT NULL,
    area_sqkm      DOUBLE CHECK (area_sqkm IS NULL OR area_sqkm >= 0),
    geom           GEOMETRY('EPSG:4326') NOT NULL
);

CREATE TABLE charging_site (
    site_id          BIGINT PRIMARY KEY,
    station_address  VARCHAR,
    postcode         VARCHAR CHECK (postcode IS NULL OR regexp_full_match(postcode, '[0-9]{4}')),
    lga_name         VARCHAR,
    latitude         DOUBLE NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude        DOUBLE NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    geom             GEOMETRY('EPSG:4326') NOT NULL,
    sa4_code         VARCHAR NOT NULL REFERENCES sa4_region(sa4_code)
);

CREATE TABLE operator (
    operator_id       INTEGER PRIMARY KEY,
    operator_name     VARCHAR NOT NULL UNIQUE,
    operator_website  VARCHAR CHECK (
        operator_website IS NULL OR starts_with(operator_website, 'https://')
    )
);

CREATE TABLE charger (
    charger_id        BIGINT PRIMARY KEY,
    site_id           BIGINT NOT NULL REFERENCES charging_site(site_id),
    operator_id       INTEGER REFERENCES operator(operator_id),
    charger_type      VARCHAR CHECK (charger_type IS NULL OR charger_type IN ('AC', 'DC')),
    charger_status    VARCHAR,
    number_of_plugs   INTEGER CHECK (number_of_plugs IS NULL OR number_of_plugs >= 0),
    cost_applies      BOOLEAN
);

CREATE TABLE charger_power_rating (
    charger_id       BIGINT REFERENCES charger(charger_id),
    component_no     INTEGER,
    connector_count  INTEGER NOT NULL CHECK (connector_count > 0),
    power_kw         DOUBLE NOT NULL CHECK (power_kw > 0),
    PRIMARY KEY (charger_id, component_no)
);

CREATE TABLE connector_type (
    connector_type_id  INTEGER PRIMARY KEY,
    connector_name     VARCHAR NOT NULL UNIQUE
);

CREATE TABLE charger_connector (
    charger_id        BIGINT REFERENCES charger(charger_id),
    connector_type_id INTEGER REFERENCES connector_type(connector_type_id),
    PRIMARY KEY (charger_id, connector_type_id)
);

-- R-tree indexes accelerate spatial filtering after the tables are populated.
CREATE INDEX idx_sa4_region_geom
ON sa4_region USING RTREE (geom);

CREATE INDEX idx_charging_site_geom
ON charging_site USING RTREE (geom);

COMMENT ON TABLE sa4_region IS 'Spatial NSW SA4 boundaries from the ABS shapefile';
COMMENT ON TABLE charging_site IS 'Coordinate-derived physical EV charging locations';
COMMENT ON TABLE operator IS 'Canonical EV charging operators';
COMMENT ON TABLE charger IS 'Cleaned TfNSW charger or installation records';
COMMENT ON TABLE charger_power_rating IS 'Power components parsed from charger ratings';
COMMENT ON TABLE connector_type IS 'Standard EV connector or plug types';
COMMENT ON TABLE charger_connector IS 'Many-to-many relationship between chargers and connector types';
