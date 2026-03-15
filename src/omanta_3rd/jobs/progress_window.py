"""最適化進捗表示ウィンドウ（Tkinter）"""

from __future__ import annotations

import sys
import threading
import time
from typing import Optional, Dict

try:
    import tkinter as tk
    from tkinter import ttk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


class ProgressWindow:
    """進捗表示用のポップアップウィンドウ"""

    def __init__(self, n_trials: int):
        if not TKINTER_AVAILABLE:
            self.root = None
            return

        self.root = tk.Tk()
        self.root.title("最適化進捗")
        self.root.geometry("500x300")
        self.root.resizable(False, False)

        # ラベル
        self.label = tk.Label(
            self.root,
            text="最適化を実行中...",
            font=("Arial", 12, "bold"),
            pady=10
        )
        self.label.pack()

        # 進捗バー
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.root,
            variable=self.progress_var,
            maximum=n_trials,
            length=400,
            mode='determinate'
        )
        self.progress_bar.pack(pady=10)

        # 進捗テキスト
        self.progress_text = tk.Label(
            self.root,
            text=f"試行: 0 / {n_trials}",
            font=("Arial", 10)
        )
        self.progress_text.pack()

        # 最良値表示
        self.best_value_label = tk.Label(
            self.root,
            text="最良値: -",
            font=("Arial", 10)
        )
        self.best_value_label.pack(pady=5)

        # 現在の試行情報
        self.current_trial_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 9),
            fg="gray"
        )
        self.current_trial_label.pack(pady=5)

        # 経過時間
        self.elapsed_time_label = tk.Label(
            self.root,
            text="経過時間: 0秒",
            font=("Arial", 9),
            fg="gray"
        )
        self.elapsed_time_label.pack(pady=5)

        self.n_trials = n_trials
        self.current_trial = 0
        self.best_value = None  # Noneで初期化（最初の値で更新）
        self.start_time = time.time()

        # ウィンドウを更新
        self.update_window()

    def update_window(self):
        """ウィンドウを更新"""
        if self.root is None:
            return

        try:
            elapsed = int(time.time() - self.start_time)
            self.elapsed_time_label.config(text=f"経過時間: {elapsed}秒")
            self.root.update()
        except:
            pass

    def update(self, trial_number: int, value: Optional[float] = None, params: Optional[Dict] = None):
        """進捗を更新"""
        if self.root is None:
            return

        self.current_trial = trial_number
        self.progress_var.set(trial_number)
        self.progress_text.config(text=f"試行: {trial_number} / {self.n_trials}")

        if value is not None:
            if self.best_value is None or value > self.best_value:
                self.best_value = value
                print(f"[ProgressWindow] 最良値が更新されました: {self.best_value:.4f}")
            if self.best_value is not None:
                self.best_value_label.config(text=f"最良値: {self.best_value:.4f}")

        if params:
            param_str = ", ".join([f"{k}={v:.3f}" for k, v in list(params.items())[:3]])
            if len(params) > 3:
                param_str += "..."
            self.current_trial_label.config(text=f"試行 {trial_number}: {param_str}")

        self.update_window()

    def close(self):
        """ウィンドウを閉じる"""
        if self.root is None:
            return

        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

    def run(self):
        """ウィンドウを実行（別スレッドで）"""
        if self.root is None:
            return

        def _update_loop():
            while self.root is not None:
                try:
                    if sys.platform == 'win32':
                        self.root.update()
                        time.sleep(0.1)
                    else:
                        self.root.mainloop()
                        break
                except Exception:
                    break

        thread = threading.Thread(target=_update_loop, daemon=True)
        thread.start()

        if sys.platform == 'win32':
            def _update_loop_win():
                while self.root is not None:
                    try:
                        self.root.update()
                        time.sleep(0.1)
                    except:
                        break

            update_thread = threading.Thread(target=_update_loop_win, daemon=True)
            update_thread.start()
