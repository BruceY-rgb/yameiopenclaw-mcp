"""
认证管理器

负责管理用户 Token 的生命周期，包括：
  - 通过 /admin-api/auth/login 登录获取 Token
  - Token 内存缓存与自动刷新
  - 多用户并发支持
"""

import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field

from src.api.client import OntuotuApiClient

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token 信息"""
    access_token: str
    expires_at: float          # Unix 时间戳，Token 过期时间
    username: str = ""


class AuthManager:
    """认证管理器

    管理用户 Token 的生命周期，提供 Token 缓存和自动刷新功能。

    使用示例：
        manager = AuthManager(api_client)
        token = await manager.get_token("user1", "pass1")
        # 后续调用会自动使用缓存，过期前自动刷新
    """

    # Token 默认有效期（秒）。腾云商旅 JWT 通常为 180 天，
    # 这里保守设置为 7200 秒（2 小时），以便及时刷新。
    DEFAULT_EXPIRES_IN = 7200

    # 提前多少秒认为 Token 即将过期，触发刷新
    REFRESH_BUFFER = 300

    def __init__(self, api_client: OntuotuApiClient):
        self.api_client = api_client
        self._cache: Dict[str, TokenInfo] = {}

    # ─────────────────────────────────────────
    # 公开接口
    # ─────────────────────────────────────────

    async def get_token(
        self,
        username: str,
        password: str,
        force_refresh: bool = False,
    ) -> str:
        """获取用户 Token（带缓存）

        步骤 4：小龙虾使用用户账号密码，调用登录接口，得到 token。

        Args:
            username: 用户名
            password: 用户密码
            force_refresh: True 时强制重新登录

        Returns:
            token 字符串
        """
        cache_key = self._cache_key(username, password)

        if not force_refresh:
            info = self._cache.get(cache_key)
            if info and time.time() < info.expires_at - self.REFRESH_BUFFER:
                logger.debug(f"使用缓存 Token: {username}")
                return info.access_token
            elif info:
                logger.debug(f"Token 即将过期，重新登录: {username}")

        return await self._do_login(username, password, cache_key)

    async def refresh_token(self, username: str, password: str) -> str:
        """强制刷新 Token"""
        cache_key = self._cache_key(username, password)
        self._cache.pop(cache_key, None)
        return await self._do_login(username, password, cache_key)

    def set_token_manually(
        self,
        username: str,
        password: str,
        token: str,
        expires_in: Optional[int] = None,
    ):
        """手动写入 Token（用于测试或外部注入）"""
        cache_key = self._cache_key(username, password)
        expires_in = expires_in or self.DEFAULT_EXPIRES_IN
        self._cache[cache_key] = TokenInfo(
            access_token=token,
            expires_at=time.time() + expires_in,
            username=username,
        )
        logger.info(f"手动写入 Token: {username}, 有效期 {expires_in}s")

    def clear_cache(self, username: Optional[str] = None):
        """清除 Token 缓存"""
        if username:
            keys = [k for k, v in self._cache.items() if v.username == username]
            for k in keys:
                del self._cache[k]
            logger.info(f"已清除用户缓存: {username}")
        else:
            self._cache.clear()
            logger.info("已清除所有 Token 缓存")

    def is_valid(self, username: str, password: str) -> bool:
        """检查 Token 是否有效"""
        info = self._cache.get(self._cache_key(username, password))
        return bool(info and time.time() < info.expires_at - self.REFRESH_BUFFER)

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total = len(self._cache)
        valid = sum(
            1 for t in self._cache.values()
            if time.time() < t.expires_at - self.REFRESH_BUFFER
        )
        return {"total": total, "valid": valid, "expired": total - valid}

    # ─────────────────────────────────────────
    # 内部方法
    # ─────────────────────────────────────────

    async def _do_login(self, username: str, password: str, cache_key: str) -> str:
        """执行登录并缓存 Token"""
        logger.info(f"正在登录用户: {username}")
        try:
            token = await self.api_client.login(
                username=username,
                password=password,
            )
            # 腾云商旅 JWT 有效期很长，这里按保守值缓存
            self._cache[cache_key] = TokenInfo(
                access_token=token,
                expires_at=time.time() + self.DEFAULT_EXPIRES_IN,
                username=username,
            )
            logger.info(f"用户登录成功: {username}")
            return token
        except Exception as e:
            logger.error(f"用户登录失败: {username}, 错误: {e}")
            raise

    @staticmethod
    def _cache_key(username: str, password: str) -> str:
        return f"{username}:{hash(password) % 1_000_000}"
