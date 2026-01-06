"""最適化結果の可視化スクリプト"""

import argparse
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances

def visualize_optimization(study_name: str):
    """
    最適化結果を可視化
    
    Args:
        study_name: スタディ名（例: optimization_20251229_140924）
    """
    # Optunaスタディを読み込み
    study = optuna.load_study(
        study_name=study_name,
        storage=f"sqlite:///optuna_{study_name}.db",
    )
    
    print(f"スタディ '{study_name}' を読み込みました")
    print(f"試行回数: {len(study.trials)}")
    print(f"最良値: {study.best_value:.4f}")
    print(f"最良試行: {study.best_trial.number}")
    print()
    
    # 最適化履歴の可視化
    try:
        print("最適化履歴を生成中...")
        fig1 = plot_optimization_history(study)
        fig1.write_image(f"optimization_history_{study_name}.png")
        print(f"✅ 最適化履歴を optimization_history_{study_name}.png に保存しました")
    except Exception as e:
        print(f"❌ 最適化履歴の生成でエラー: {e}")
    
    # パラメータ重要度の可視化
    try:
        print("パラメータ重要度を生成中...")
        fig2 = plot_param_importances(study)
        fig2.write_image(f"param_importances_{study_name}.png")
        print(f"✅ パラメータ重要度を param_importances_{study_name}.png に保存しました")
    except Exception as e:
        print(f"❌ パラメータ重要度の生成でエラー: {e}")
    
    print()
    print("可視化が完了しました！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="最適化結果の可視化")
    parser.add_argument(
        "--study-name",
        type=str,
        default="optimization_20251229_140924",
        help="スタディ名（デフォルト: optimization_20251229_140924）"
    )
    
    args = parser.parse_args()
    visualize_optimization(args.study_name)















