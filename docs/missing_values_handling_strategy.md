# 財務データ欠損値の対処法に関する調査結果と提案

## 0. 調査結果の要約

### 0.1 J-Quants APIに特化した議論について

**調査結果**: J-Quants APIのデータ欠損について、Web上で具体的に議論されている情報は**見つかりませんでした**。

検索した内容:
- J-Quants APIの公式ドキュメント
- GitHubリポジトリやIssues
- コミュニティフォーラムや質問サイト
- 技術ブログや記事

**結論**: 
- J-Quants APIのデータ欠損について、公開された議論や公式の注意事項は見つかりませんでした
- これは、欠損値が**APIの仕様として想定されている**可能性、または**ユーザーが個別に対処している**可能性を示唆しています

### 0.2 一般的な財務データの欠損値について

一方で、**一般的な財務データや統計データにおける欠損値の問題**は広く議論されており、多くの対処法が提案されています。

## 1. 調査結果のまとめ

### 1.1 Web上での一般的な議論

財務データの欠損値については、データ分析・機械学習の分野で広く議論されており、以下のような対処法が提案されています：

#### 主な対処法の分類

1. **削除法（Listwise Deletion）**
   - 欠損値を含むデータポイントを削除
   - データ量が減少し、統計的なパワーが低下する可能性

2. **単純代入法（Simple Imputation）**
   - 平均値・中央値・最頻値による補完
   - 簡便だが、データの分散を過小評価する可能性

3. **回帰代入法（Regression Imputation）**
   - 他の変数との関係性を利用して欠損値を予測
   - より精度の高い補完が期待できる

4. **多重代入法（Multiple Imputation）**
   - 欠損値を複数回補完し、複数のデータセットを作成
   - 補完による不確実性を考慮した分析が可能

5. **機械学習を用いた補完**
   - 決定木、k近傍法、ランダムフォレスト（MissForest）など
   - 複雑なデータ構造にも対応可能

### 1.2 欠損値の種類（MCAR, MAR, MNAR）

- **MCAR（完全にランダムな欠損）**: 欠損が他のデータと無関係にランダムに発生
- **MAR（ランダムな欠損）**: 欠損が観測されたデータに関連しているが、欠損値自体には関連していない
- **MNAR（非ランダムな欠損）**: 欠損が欠損データの固有の値に関連している

### 1.3 日本の財務データにおける欠損値の特徴

#### 確認された欠損パターン

1. **完全にデータが欠損している銘柄**
   - 例: 1773（FYデータが存在しない）
   - 原因: 上場廃止、データ取得エラー、新規上場など

2. **一部カラムがNULL**
   - 例: 2130（`equity`, `shares_outstanding`, `treasury_shares`がNULL）
   - 例: 2282（`operating_profit`がNULL）
   - 原因: 
     - 中小企業で開示されない項目がある
     - 業種によって開示義務が異なる
     - 会計基準の違い

3. **予想データが古い/欠損**
   - 多くの銘柄で最新の予想データが2019-2020年のもの
   - 原因: 予想値の開示が不定期、または開示されていない

## 2. 現在の実装状況

### 2.1 既存の対処法

現在のコード（`monthly_run.py`）では、以下の対処が実装されています：

```python
# パーセンタイルランクベースのスコア: 0.5（中立）で補完
df["value_score"] = df["value_score"].fillna(0.5)
df["growth_score"] = df["growth_score"].fillna(0.5)
df["size_score"] = df["size_score"].fillna(0.5)

# ROE: 0.0で補完（後でROE>=0.1のフィルタで除外）
df["quality_score"] = df["quality_score"].fillna(0.0)

# record_high_score: 0.0で補完
df["record_high_score"] = df["record_high_score"].fillna(0.0)

# Core score: 0.0で補完
df["core_score"] = df["core_score"].fillna(0.0)
```

### 2.2 現在の対処法の特徴

- **保守的なアプローチ**: 欠損値は低スコア（0.0）または中立スコア（0.5）で補完
- **フィルタリング**: ROE >= 0.1のハードフィルタで、ROEが欠損している銘柄を除外
- **問題点**: 
  - 欠損値を持つ銘柄が不利になる（スコアが低下）
  - 一部のデータが欠損していても、他の指標が優秀な銘柄が除外される可能性

## 3. 提案される対処法

### 3.1 短期的な改善（実装容易）

#### A. セクター別の中央値補完

```python
# equityが欠損している場合、同セクターの中央値で補完
df["equity"] = df.groupby("sector33")["equity"].transform(
    lambda x: x.fillna(x.median())
)

# shares_outstandingが欠損している場合、同セクターの中央値で補完
df["shares_outstanding"] = df.groupby("sector33")["shares_outstanding"].transform(
    lambda x: x.fillna(x.median())
)
```

**メリット**:
- 実装が簡単
- セクター特性を考慮した補完が可能

**デメリット**:
- セクター内のばらつきを無視
- 極端な値を持つ銘柄の影響を受けやすい

#### B. 時系列補完（過去データから推定）

```python
# 過去のFYデータから最新値を推定
# 例: equityが欠損している場合、前回のequity * (1 + 平均成長率)で推定
```

**メリット**:
- 時系列のトレンドを考慮
- より現実的な補完が可能

**デメリット**:
- 過去データが必要
- 計算コストが高い

#### C. 相関変数による補完

```python
# equityが欠損している場合、market_capとprofitから推定
# equity ≈ market_cap / PBR（セクター平均）
# または: equity ≈ profit / ROE（セクター平均）
```

**メリット**:
- 財務指標間の関係性を利用
- より精度の高い補完が期待できる

**デメリット**:
- 補完に使用する変数自体が欠損している場合に対応できない

### 3.2 中期的な改善（実装中程度）

#### D. k近傍法（k-NN）による補完

```python
from sklearn.impute import KNNImputer

# 類似した銘柄（セクター、規模、収益性など）から欠損値を推定
imputer = KNNImputer(n_neighbors=5)
df_imputed = imputer.fit_transform(df[relevant_columns])
```

**メリット**:
- 複数の変数を同時に考慮
- より精度の高い補完が期待できる

**デメリット**:
- 計算コストが高い
- 類似銘柄の定義が難しい

#### E. 回帰モデルによる補完

```python
from sklearn.ensemble import RandomForestRegressor

# equityが欠損している場合、他の財務指標から予測
# 例: equity = f(profit, operating_profit, market_cap, sector)
```

**メリット**:
- 非線形な関係性も捉えられる
- 精度の高い補完が期待できる

**デメリット**:
- モデルの訓練が必要
- 過学習のリスク

### 3.3 長期的な改善（実装困難）

#### F. 多重代入法（Multiple Imputation）

```python
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer

# 複数の補完データセットを作成し、分析結果を統合
imputer = IterativeImputer(random_state=42)
df_imputed = imputer.fit_transform(df[relevant_columns])
```

**メリット**:
- 補完による不確実性を考慮
- より信頼性の高い分析が可能

**デメリット**:
- 実装が複雑
- 計算コストが非常に高い

## 4. 推奨される実装方針

### 4.1 段階的なアプローチ

1. **第1段階（即座に実装可能）**:
   - セクター別中央値補完を実装
   - 予想データが古い場合の警告ログを追加

2. **第2段階（1-2週間で実装）**:
   - 相関変数による補完を実装
   - 補完の精度を検証

3. **第3段階（1-2ヶ月で実装）**:
   - k-NNまたは回帰モデルによる補完を実装
   - バックテストで補完の影響を評価

### 4.2 実装時の注意点

1. **補完の記録**: どの変数が補完されたかを記録し、後で分析できるようにする
2. **補完の検証**: 補完後のデータが元のデータの特性を維持しているかを確認
3. **段階的な適用**: 一度に全ての補完を実装せず、段階的に適用して影響を確認

### 4.3 補完しない選択肢

以下の場合は、補完せずに除外することを検討：

- **完全にデータが欠損している銘柄**: 1773のようにFYデータが全く存在しない
- **必須指標が欠損**: ROE計算に必要な`equity`と`profit`の両方が欠損
- **予想データが5年以上古い**: 信頼性が低いため除外

## 5. 具体的な実装例

### 5.1 セクター別中央値補完の実装例

```python
def impute_missing_values_by_sector(df: pd.DataFrame) -> pd.DataFrame:
    """セクター別の中央値で欠損値を補完"""
    df = df.copy()
    
    # equityの補完
    if "equity" in df.columns:
        df["equity"] = df.groupby("sector33")["equity"].transform(
            lambda x: x.fillna(x.median())
        )
    
    # shares_outstandingの補完
    if "shares_outstanding" in df.columns:
        df["shares_outstanding"] = df.groupby("sector33")["shares_outstanding"].transform(
            lambda x: x.fillna(x.median())
        )
    
    # treasury_sharesの補完（0で補完）
    if "treasury_shares" in df.columns:
        df["treasury_shares"] = df["treasury_shares"].fillna(0.0)
    
    return df
```

### 5.2 相関変数による補完の実装例

```python
def impute_equity_from_market_cap(df: pd.DataFrame) -> pd.DataFrame:
    """market_capとセクター平均PBRからequityを推定"""
    df = df.copy()
    
    # セクター別の平均PBRを計算
    sector_pbr = df.groupby("sector33").apply(
        lambda g: (g["market_cap"] / g["equity"]).median()
    ).to_dict()
    
    # equityが欠損している場合、market_cap / セクター平均PBRで補完
    mask = df["equity"].isna() & df["market_cap"].notna()
    for sector, avg_pbr in sector_pbr.items():
        sector_mask = mask & (df["sector33"] == sector)
        if avg_pbr > 0 and not pd.isna(avg_pbr):
            df.loc[sector_mask, "equity"] = df.loc[sector_mask, "market_cap"] / avg_pbr
    
    return df
```

## 6. 参考文献

- [欠損データの正しい対処手法: 実務で使える理論と方法](https://book.st-hakky.com/data-science/missing-values-in-datasets/)
- [データ分析における欠損値の管理](https://scisimple.com/ja/articles/2025-08-12-fen-xi-niokeruqian-sun-detanoguan-li--ak4j758)
- [多重代入法による欠損値処理](https://bellcurve.jp/statistics/blog/14238.html)
- [時系列データの欠損値補完](https://scisimple.com/ja/articles/2025-06-22-shi-xi-lie-detanoqian-sun-zhi-womai-merutamenogao-du-natekunitsuku--ak42vr0)

## 7. 結論

財務データの欠損値は、データ取得の問題ではなく、**企業の開示状況や業種特性によるもの**である可能性が高いです。

**推奨されるアプローチ**:
1. **短期的**: セクター別中央値補完を実装
2. **中期的**: 相関変数による補完を追加
3. **長期的**: 機械学習による補完を検討

ただし、**補完は慎重に行うべき**であり、補完の影響を定期的に評価し、必要に応じて調整することが重要です。

