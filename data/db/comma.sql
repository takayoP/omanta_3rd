DROP VIEW IF EXISTS v_fins_statements_fmt;

CREATE VIEW v_fins_statements_fmt AS
SELECT
  fs.disclosed_date,
  fs.disclosed_time,
  fs.code,
  fs.type_of_current_period,
  fs.current_period_end,

  -- カンマ対象（列名は元のまま）
  CASE WHEN fs.operating_profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.operating_profit) AS INTEGER)) END AS operating_profit,
  CASE WHEN fs.profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.profit) AS INTEGER)) END AS profit,
  CASE WHEN fs.equity IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.equity) AS INTEGER)) END AS equity,

  -- そのまま
  fs.eps,
  fs.bvps,

  -- カンマ対象（列名は元のまま）
  CASE WHEN fs.forecast_operating_profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.forecast_operating_profit) AS INTEGER)) END AS forecast_operating_profit,
  CASE WHEN fs.forecast_profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.forecast_profit) AS INTEGER)) END AS forecast_profit,

  -- そのまま
  fs.forecast_eps,

  -- カンマ対象（列名は元のまま）
  CASE WHEN fs.next_year_forecast_operating_profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.next_year_forecast_operating_profit) AS INTEGER)) END AS next_year_forecast_operating_profit,
  CASE WHEN fs.next_year_forecast_profit IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.next_year_forecast_profit) AS INTEGER)) END AS next_year_forecast_profit,

  -- そのまま
  fs.next_year_forecast_eps,

  -- カンマ対象（列名は元のまま）
  CASE WHEN fs.shares_outstanding IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.shares_outstanding) AS INTEGER)) END AS shares_outstanding,
  CASE WHEN fs.treasury_shares IS NULL THEN NULL
       ELSE printf('%,d', CAST(ROUND(fs.treasury_shares) AS INTEGER)) END AS treasury_shares

FROM fins_statements fs;
