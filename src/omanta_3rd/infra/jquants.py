import time
import requests
from typing import Optional, Dict, Any, List
from functools import wraps

from ..config.settings import (
    JQUANTS_REFRESH_TOKEN,
    JQUANTS_MAILADDRESS,
    JQUANTS_PASSWORD,
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
        refresh_token: Optional[str] = None,
        mailaddress: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.refresh_token = refresh_token or JQUANTS_REFRESH_TOKEN
        self.mailaddress = mailaddress or JQUANTS_MAILADDRESS
        self.password = password or JQUANTS_PASSWORD

        self.id_token: Optional[str] = None
        self.id_token_expires_at: float = 0.0  # 自前で管理（24h想定）:contentReference[oaicite:6]{index=6}

        # refresh token が無いなら、mail/pass が必要 :contentReference[oaicite:7]{index=7}
        if not self.refresh_token and not (self.mailaddress and self.password):
            raise ValueError("refresh token か mailaddress/password が必要です")

    def _issue_refresh_token(self) -> str:
        """mail/password から refreshToken を取得"""
        url = f"{JQUANTS_API_BASE_URL}/token/auth_user"
        payload = {"mailaddress": self.mailaddress, "password": self.password}
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        j = r.json()
        token = j.get("refreshToken")
        if not token:
            raise JQuantsAPIError(f"refreshTokenが取得できません: keys={list(j.keys())}")
        self.refresh_token = token
        return token

    def _issue_id_token(self) -> str:
        # A運用：毎回 refreshToken を取り直す（1週間失効対策）
        self._issue_refresh_token()
        url = f"{JQUANTS_API_BASE_URL}/token/auth_refresh"
        r = requests.post(url, params={"refreshtoken": self.refresh_token}, timeout=30)
        r.raise_for_status()
        j = r.json()
        token = j.get("idToken")
        if not token:
            raise JQuantsAPIError(f"idTokenが取得できません: keys={list(j.keys())}")

        self.id_token = token
        # idTokenは24時間（公式）。安全側に23時間で更新する :contentReference[oaicite:9]{index=9}
        self.id_token_expires_at = time.time() + 23 * 60 * 60
        return token

    def _get_id_token(self) -> str:
        if self.id_token and time.time() < self.id_token_expires_at:
            return self.id_token
        return self._issue_id_token()

    @retry(max_attempts=3, delay=1.0)
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        pagination_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        id_token = self._get_id_token()
        url = f"{JQUANTS_API_BASE_URL}{endpoint}"

        q = dict(params or {})
        if pagination_key:
            q["pagination_key"] = pagination_key

        headers = {"Authorization": f"Bearer {id_token}"}  # これだけ :contentReference[oaicite:10]{index=10}
        r = requests.get(url, headers=headers, params=q, timeout=60)

        # 401なら idToken 再発行して1回だけリトライ
        if r.status_code == 401:
            self.id_token = None
            id_token = self._issue_id_token()
            headers = {"Authorization": f"Bearer {id_token}"}
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
        /listed/info はレスポンスキーが "info" :contentReference[oaicite:11]{index=11}
        """
        all_rows: List[Dict[str, Any]] = []
        pagination_key = None

        while True:
            j = self.get(endpoint, params=params, pagination_key=pagination_key)

            # エンドポイントごとの配列キーを自動検出（pagination_key/message以外の最初のlist）
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

            time.sleep(0.3)

        return all_rows
