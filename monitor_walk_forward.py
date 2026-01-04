#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis 実行中の監視スクリプト（Python版）
CPU利用率、メモリ使用量、プロセス数を監視します
"""

import time
import sys
import platform
from datetime import datetime
from typing import Dict, List, Optional

try:
    import psutil
except ImportError:
    print("psutilがインストールされていません。以下のコマンドでインストールしてください:")
    print("  pip install psutil")
    sys.exit(1)


def format_bytes(bytes_value: int) -> str:
    """バイト数を読みやすい形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def get_python_processes() -> List[Dict]:
    """Pythonプロセスの情報を取得"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'create_time']):
        try:
            pinfo = proc.info
            if 'python' in pinfo['name'].lower():
                mem_info = pinfo['memory_info']
                if mem_info and mem_info.rss > 1 * 1024 * 1024 * 1024:  # 1GB以上
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'memory_mb': mem_info.rss / (1024 * 1024),
                        'memory_gb': mem_info.rss / (1024 * 1024 * 1024),
                        'cpu_percent': pinfo.get('cpu_percent', 0),
                        'create_time': datetime.fromtimestamp(pinfo['create_time']).strftime('%Y-%m-%d %H:%M:%S'),
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return processes


def monitor_walk_forward(interval: int = 5, min_memory_gb: float = 1.0):
    """
    Walk-Forward Analysis実行中の監視
    
    Args:
        interval: 更新間隔（秒、デフォルト: 5）
        min_memory_gb: 表示する最小メモリ使用量（GB、デフォルト: 1.0）
    """
    print("=" * 80)
    print("Walk-Forward Analysis Monitor (Python版)")
    print("=" * 80)
    print()
    print("監視項目:")
    print("  1. Pythonプロセスのメモリ使用量")
    print("  2. CPU利用率")
    print("  3. システム全体のメモリ使用量")
    print("  4. プロセス数")
    print()
    print(f"更新間隔: {interval}秒")
    print(f"最小メモリ表示: {min_memory_gb}GB以上")
    print()
    print("停止方法: Ctrl+C")
    print()
    
    iteration = 0
    prev_cpu_times = {}  # {pid: cpu_times}
    
    try:
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print("=" * 80)
            print(f"[{timestamp}] Monitor #{iteration}")
            print("=" * 80)
            
            # Pythonプロセスを取得
            python_procs = get_python_processes()
            
            if python_procs:
                # メモリ使用量でソート
                python_procs.sort(key=lambda x: x['memory_gb'], reverse=True)
                
                print()
                print(f"Pythonプロセス ({min_memory_gb}GB以上): {len(python_procs)}個")
                print("-" * 80)
                print(f"{'PID':<8} {'メモリ(GB)':<12} {'CPU(%)':<10} {'開始時刻':<20}")
                print("-" * 80)
                
                total_memory_gb = 0.0
                total_cpu_percent = 0.0
                
                for proc in python_procs:
                    if proc['memory_gb'] >= min_memory_gb:
                        print(f"{proc['pid']:<8} {proc['memory_gb']:>10.2f} {proc['cpu_percent']:>8.1f}% {proc['create_time']:<20}")
                        total_memory_gb += proc['memory_gb']
                        total_cpu_percent += proc['cpu_percent']
                
                print("-" * 80)
                print(f"{'合計':<8} {total_memory_gb:>10.2f} {total_cpu_percent:>8.1f}%")
                
                # 警告チェック
                if total_memory_gb > 50:
                    print()
                    print("⚠️  警告: メモリ使用量が50GBを超えています！", file=sys.stderr)
                elif total_memory_gb > 45:
                    print()
                    print("⚠️  注意: メモリ使用量が45GBを超えています")
            else:
                print()
                print(f"Pythonプロセスが見つかりません（{min_memory_gb}GB以上のメモリを使用しているプロセス）")
            
            # システム全体のメモリ使用量
            mem = psutil.virtual_memory()
            print()
            print("システム全体のメモリ:")
            print(f"  合計: {format_bytes(mem.total)}")
            print(f"  使用中: {format_bytes(mem.used)} ({mem.percent:.1f}%)")
            print(f"  利用可能: {format_bytes(mem.available)}")
            print(f"  空き: {format_bytes(mem.free)}")
            
            if mem.percent > 90:
                print()
                print("⚠️  警告: システムメモリ使用率が90%を超えています！", file=sys.stderr)
            elif mem.percent > 80:
                print()
                print("⚠️  注意: システムメモリ使用率が80%を超えています")
            
            # CPU利用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            print()
            print(f"CPU利用率:")
            print(f"  全体: {cpu_percent:.1f}%")
            print(f"  CPUコア数: {cpu_count}")
            if len(cpu_per_core) <= 8:  # 8コア以下なら各コアを表示
                print(f"  コア別: {', '.join([f'{c:.1f}%' for c in cpu_per_core])}")
            
            # ディスクI/O（簡易）
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    print()
                    print("ディスクI/O:")
                    print(f"  読み込み: {format_bytes(disk_io.read_bytes)}")
                    print(f"  書き込み: {format_bytes(disk_io.write_bytes)}")
            except Exception:
                pass  # ディスクI/O情報が取得できない場合はスキップ
            
            print()
            print(f"次回更新まで{interval}秒待機...")
            print()
            
            sys.stdout.flush()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("監視を停止しました")
        print("=" * 80)
        sys.exit(0)
    except Exception as e:
        print()
        print(f"❌ エラーが発生しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Walk-Forward Analysis実行中の監視スクリプト"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="更新間隔（秒、デフォルト: 5）",
    )
    parser.add_argument(
        "--min-memory-gb",
        type=float,
        default=1.0,
        help="表示する最小メモリ使用量（GB、デフォルト: 1.0）",
    )
    
    args = parser.parse_args()
    
    monitor_walk_forward(interval=args.interval, min_memory_gb=args.min_memory_gb)


