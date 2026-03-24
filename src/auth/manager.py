"""
认证管理器

负责管理用户Token生命周期，包括Token生成、缓存、自动刷新等功能。
"""

import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field

from src.api.client import MeiyaApiClient

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token信息"""
    access_token: str
    refresh_token: Optional[str]
    expires_at: float
    token_type: str = "Bearer"
    user_id: Optional[str] = None


class AuthManager:
    """认证管理器

    负责管理用户Token的生命周期，提供Token缓存和自动刷新功能。
    """

    def __init__(self, api_client: MeiyaApiClient):
        """初始化认证管理器

        Args:
            api_client: API客户端实例
        """
        self.api_client = api_client
        self._token_cache: Dict[str, TokenInfo] = {}
        self._buffer_seconds = 300  # 提前5分钟过期
        self._default_expires_in = 7200  # 默认2小时

    async def get_user_token(
        self,
        user_id: str,
        password: str,
        force_refresh: bool = False
    ) -> str:
        """获取用户Token（带缓存）

        Args:
            user_id: 用户ID
            password: 用户密码
            force_refresh: 强制刷新Token

        Returns:
            access_token
        """
        cache_key = self._get_cache_key(user_id, password)

        # 检查缓存
        if not force_refresh and cache_key in self._token_cache:
            token_info = self._token_cache[cache_key]
            if time.time() < token_info.expires_at - self._buffer_seconds:
                logger.debug(f"使用缓存的Token: {user_id}")
                return token_info.access_token
            else:
                logger.debug(f"Token即将过期: {user_id}")

        # 调用登录接口
        logger.info(f"正在登录用户: {user_id}")

        try:
            response = await self.api_client.request(
                "POST",
                "/auth/login",
                json={
                    "userId": user_id,
                    "password": password
                }
            )

            data = response.get("data", {})
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", self._default_expires_in)

            # 缓存Token
            token_info = TokenInfo(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=time.time() + expires_in,
                user_id=user_id
            )
            self._token_cache[cache_key] = token_info

            logger.info(f"用户登录成功: {user_id}, Token有效期: {expires_in}秒")
            return access_token

        except Exception as e:
            logger.error(f"用户登录失败: {user_id}, 错误: {e}")
            raise

    async def refresh_user_token(self, user_id: str, password: str) -> str:
        """刷新用户Token

        Args:
            user_id: 用户ID
            password: 用户密码

        Returns:
            新的access_token
        """
        cache_key = self._get_cache_key(user_id, password)

        # 清除缓存
        if cache_key in self._token_cache:
            del self._token_cache[cache_key]

        # 重新获取
        return await self.get_user_token(user_id, password, force_refresh=True)

    def clear_cache(self, user_id: Optional[str] = None):
        """清除Token缓存

        Args:
            user_id: 指定用户ID，None表示清除所有
        """
        if user_id:
            # 清除指定用户的缓存
            keys_to_remove = [
                k for k, v in self._token_cache.items()
                if v.user_id == user_id
            ]
            for key in keys_to_remove:
                del self._token_cache[key]
            logger.info(f"已清除用户缓存: {user_id}")
        else:
            self._token_cache.clear()
            logger.info("已清除所有Token缓存")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息

        Returns:
            缓存统计
        """
        total = len(self._token_cache)
        expired = sum(
            1 for t in self._token_cache.values()
            if time.time() >= t.expires_at - self._buffer_seconds
        )
        valid = total - expired

        return {
            "total": total,
            "valid": valid,
            "expired": expired
        }

    def _get_cache_key(self, user_id: str, password: str) -> str:
        """生成缓存Key"""
        return f"{user_id}:{hash(password) % 100000}"

    def is_token_valid(self, user_id: str, password: str) -> bool:
        """检查Token是否有效

        Args:
            user_id: 用户ID
            password: 用户密码

        Returns:
            Token是否有效
        """
        cache_key = self._get_cache_key(user_id, password)
        if cache_key not in self._token_cache:
            return False

        token_info = self._token_cache[cache_key]
        return time.time() < token_info.expires_at - self._buffer_seconds

    def get_token_info(self, user_id: str, password: str) -> Optional[TokenInfo]:
        """获取Token信息

        Args:
            user_id: 用户ID
            password: 用户密码

        Returns:
            Token信息，如果不存在返回None
        """
        cache_key = self._get_cache_key(user_id, password)
        return self._token_cache.get(cache_key)

    def set_token(
        self,
        user_id: str,
        password: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ):
        """手动设置Token（用于测试或外部Token）

        Args:
            user_id: 用户ID
            password: 用户密码
            access_token: 访问令牌
            refresh_token: 刷新令牌
            expires_in: 有效期（秒）
        """
        cache_key = self._get_cache_key(user_id, password)
        expires_in = expires_in or self._default_expires_in

        token_info = TokenInfo(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=time.time() + expires_in,
            user_id=user_id
        )
        self._token_cache[cache_key] = token_info

        logger.info(f"手动设置Token: {user_id}, 有效期: {expires_in}秒")
