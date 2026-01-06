-- バックテストパフォーマンステーブルに品質指標カラムを追加
-- num_stocks_with_return: 有効なリターンがある銘柄数
-- weight_coverage: 有効weight割合（品質指標）

ALTER TABLE backtest_performance 
ADD COLUMN num_stocks_with_return INTEGER;

ALTER TABLE backtest_performance 
ADD COLUMN weight_coverage REAL;















