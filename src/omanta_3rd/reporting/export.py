"""CSV/JSON/簡易HTMLなどの出力"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..infra.db import connect_db


def export_portfolio_csv(
    rebalance_date: str,
    output_path: Optional[Path] = None,
) -> Path:
    """
    ポートフォリオをCSVで出力
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        output_path: 出力パス（Noneの場合は自動生成）
        
    Returns:
        出力ファイルパス
    """
    if output_path is None:
        output_path = Path(f"portfolio_{rebalance_date}.csv")
    
    with connect_db(read_only=True) as conn:
        sql = """
            SELECT p.*, li.company_name, li.sector33
            FROM portfolio_monthly p
            LEFT JOIN listed_info li ON p.code = li.code AND li.date = (
                SELECT MAX(date) FROM listed_info WHERE code = p.code AND date <= p.rebalance_date
            )
            WHERE p.rebalance_date = ?
            ORDER BY p.weight DESC
        """
        rows = conn.execute(sql, (rebalance_date,)).fetchall()
        
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            if not rows:
                return output_path
            
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
    
    return output_path


def export_portfolio_json(
    rebalance_date: str,
    output_path: Optional[Path] = None,
) -> Path:
    """
    ポートフォリオをJSONで出力
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        output_path: 出力パス（Noneの場合は自動生成）
        
    Returns:
        出力ファイルパス
    """
    if output_path is None:
        output_path = Path(f"portfolio_{rebalance_date}.json")
    
    with connect_db(read_only=True) as conn:
        sql = """
            SELECT p.*, li.company_name, li.sector33
            FROM portfolio_monthly p
            LEFT JOIN listed_info li ON p.code = li.code AND li.date = (
                SELECT MAX(date) FROM listed_info WHERE code = p.code AND date <= p.rebalance_date
            )
            WHERE p.rebalance_date = ?
            ORDER BY p.weight DESC
        """
        rows = conn.execute(sql, (rebalance_date,)).fetchall()
        
        data = [dict(row) for row in rows]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return output_path


def export_portfolio_html(
    rebalance_date: str,
    output_path: Optional[Path] = None,
) -> Path:
    """
    ポートフォリオを簡易HTMLで出力
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        output_path: 出力パス（Noneの場合は自動生成）
        
    Returns:
        出力ファイルパス
    """
    if output_path is None:
        output_path = Path(f"portfolio_{rebalance_date}.html")
    
    with connect_db(read_only=True) as conn:
        sql = """
            SELECT p.*, li.company_name, li.sector33
            FROM portfolio_monthly p
            LEFT JOIN listed_info li ON p.code = li.code AND li.date = (
                SELECT MAX(date) FROM listed_info WHERE code = p.code AND date <= p.rebalance_date
            )
            WHERE p.rebalance_date = ?
            ORDER BY p.weight DESC
        """
        rows = conn.execute(sql, (rebalance_date,)).fetchall()
        
        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>ポートフォリオ - {rebalance_date}</title>
    <style>
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>ポートフォリオ - {rebalance_date}</h1>
    <table>
        <thead>
            <tr>
                <th>銘柄コード</th>
                <th>会社名</th>
                <th>業種</th>
                <th>ウェイト</th>
                <th>Core Score</th>
                <th>Entry Score</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for row in rows:
            html += f"""
            <tr>
                <td>{row['code']}</td>
                <td>{row['company_name'] or ''}</td>
                <td>{row['sector33'] or ''}</td>
                <td>{row['weight']:.2%}</td>
                <td>{row['core_score']:.3f if row['core_score'] else ''}</td>
                <td>{row['entry_score']:.3f if row['entry_score'] else ''}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
</body>
</html>
"""
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
    
    return output_path


