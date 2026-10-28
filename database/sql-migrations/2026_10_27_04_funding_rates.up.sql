-- Funding de Bybit (perpetuos lineales) para el backtest.
--   funding_rates: una fila por liquidación (rate > 0: el long paga al short).
--   funding_coverage: tramo [covered_from, covered_to] ya descargado por símbolo. Entre dos liquidaciones
--   no hay filas, así que sin esta tabla no se distingue "no hubo funding" de "no se descargó".
CREATE TABLE IF NOT EXISTS funding_rates (
    symbol       varchar(30)      NOT NULL,
    funding_time timestamptz      NOT NULL,
    rate         double precision NOT NULL,
    PRIMARY KEY (symbol, funding_time)
);
CREATE TABLE IF NOT EXISTS funding_coverage (
    symbol       varchar(30) PRIMARY KEY,
    covered_from timestamptz NOT NULL,
    covered_to   timestamptz NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (covered_from <= covered_to)
);
