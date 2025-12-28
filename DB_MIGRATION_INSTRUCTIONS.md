# データベースマイグレーション手順

## index_dailyテーブルの追加

指数データ（日経平均指数など）を保存する`index_daily`テーブルを既存のデータベースに追加する場合、以下のマイグレーションスクリプトを実行してください。

### 実行方法

```bash
python -m src.omanta_3rd.jobs.run_migration sql/migration_add_index_daily.sql
```

または、直接パスを指定：

```bash
python -m src.omanta_3rd.jobs.run_migration sql\migration_add_index_daily.sql
```

### マイグレーション内容

- `index_daily`テーブルの作成
  - カラム: `date`, `index_code`, `open`, `high`, `low`, `close`
  - 主キー: `(date, index_code)`
- インデックスの作成: `idx_index_date_code`

### 注意事項

- `CREATE TABLE IF NOT EXISTS`を使用しているため、既にテーブルが存在する場合はスキップされます
- 既存のデータには影響しません
- マイグレーション実行後、`update_all_data.py --target indices`で指数データを取得できます
