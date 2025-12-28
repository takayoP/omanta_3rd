import time
import requests
from typing import Optional, Dict, Any, List
from functools import wraps

from ..config.settings import (
    JQUANTS_API_KEY,
    JQUANTS_API_BASE_URL,
)


class JQuantsAPIError(Exception):
    pass


def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, JQuantsAPIError) as e:
                    last = e
                    if i < max_attempts - 1:
                        time.sleep(delay * (i + 1))
                    else:
                        raise
            raise last
        return wrapper
    return decorator


class JQuantsClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        requests_per_minute: int = 120,
    ):
        """
        J-Quants API V2 クライアント
        
        Args:
            api_key: APIキー（未指定の場合は環境変数JQUANTS_API_KEYを使用）
            requests_per_minute: 1分あたりのリクエスト制限（デフォルト: 120）
        """
        self.api_key = api_key or JQUANTS_API_KEY
        if not self.api_key:
            raise ValueError("APIキーが必要です。環境変数JQUANTS_API_KEYを設定するか、api_key引数を指定してください。")
        
        # レート制限管理: 120リクエスト/分 = 0.5秒/リクエスト（60秒 / 120リクエスト）
        self.min_request_interval = 60.0 / requests_per_minute
        self.last_request_time: float = 0.0

    def _wait_for_rate_limit(self):
        """レート制限を守るために必要な待機時間を確保"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    @retry(max_attempts=3, delay=1.0)
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        pagination_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GETリクエストを実行（V2 API）
        
        Args:
            endpoint: APIエンドポイント（例: "/equities/master"）
            params: クエリパラメータ
            pagination_key: ページネーションキー
            
        Returns:
            APIレスポンス（JSON）
        """
        # レート制限を守るために待機
        self._wait_for_rate_limit()
        
        url = f"{JQUANTS_API_BASE_URL}{endpoint}"

        q = dict(params or {})
        if pagination_key:
            q["pagination_key"] = pagination_key

        # V2 APIではAPIキーをx-api-keyヘッダーで送信
        headers = {"x-api-key": self.api_key}
        r = requests.get(url, headers=headers, params=q, timeout=60)

        if r.status_code == 429:
            # レート制限：少し待ってから例外にしてretryデコレータに渡す
            time.sleep(2.0)
            raise JQuantsAPIError(f"Rate limit (429): {r.text[:200]}")

        if r.status_code >= 400:
            error_msg = f"HTTP {r.status_code}: {r.url}\n"
            try:
                error_detail = r.json()
                error_msg += f"詳細: {error_detail}"
            except:
                error_msg += f"レスポンス: {r.text[:500]}"
            raise JQuantsAPIError(error_msg)
        
        r.raise_for_status()
        return r.json()

    def get_all_pages(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        pagination_key があるAPIに対応。
        V2 APIではレスポンスキーが "data" に統一されている
        """
        all_rows: List[Dict[str, Any]] = []
        pagination_key = None

        while True:
            j = self.get(endpoint, params=params, pagination_key=pagination_key)

            # V2 APIでは"data"キーで統一されている
            if "data" in j and isinstance(j["data"], list):
                all_rows.extend(j["data"])
            else:
                # フォールバック: エンドポイントごとの配列キーを自動検出
                list_key = None
                for k, v in j.items():
                    if k in ("pagination_key", "message"):
                        continue
                    if isinstance(v, list):
                        list_key = k
                        break
                
                if list_key:
                    all_rows.extend(j[list_key])
                else:
                    # 予期しない場合は丸ごと
                    all_rows.append(j)

            pagination_key = j.get("pagination_key")
            if not pagination_key:
                break

            # ページネーション時もレート制限管理により適切な間隔が保たれるため、
            # 追加の待機は不要（get()内で既に待機済み）

        return all_rows
