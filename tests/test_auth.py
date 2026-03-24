"""
认证管理器测试

测试 AuthManager 类的功能，包括：
- Token缓存
- Token刷新
- 缓存管理
- Token有效性检查
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.manager import AuthManager, TokenInfo
from src.api.client import MeiyaApiError


# ===========================================
# Token缓存测试
# ===========================================

class TestTokenCache:
    """测试Token缓存功能"""

    @pytest.mark.asyncio
    async def test_get_user_token_first_time(self, auth_manager):
        """测试首次获取Token"""
        auth_manager.api_client.request = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "access_token": "test_token_12345",
                    "refresh_token": "refresh_token_67890",
                    "expires_in": 7200
                }
            }
        )

        token = await auth_manager.get_user_token(
            user_id="test_user",
            password="test_password"
        )

        assert token == "test_token_12345"
        assert len(auth_manager._token_cache) == 1

    @pytest.mark.asyncio
    async def test_get_user_token_cached(self, auth_manager, mock_token_info):
        """测试使用缓存的Token"""
        # 预先设置缓存
        cache_key = auth_manager._get_cache_key("test_user", "test_password")
        auth_manager._token_cache[cache_key] = mock_token_info

        token = await auth_manager.get_user_token(
            user_id="test_user",
            password="test_password"
        )

        # 应该使用缓存，不调用API
        assert token == mock_token_info.access_token
        auth_manager.api_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_token_force_refresh(self, auth_manager, mock_token_info):
        """测试强制刷新Token"""
        # 预先设置缓存
        cache_key = auth_manager._get_cache_key("test_user", "test_password")
        auth_manager._token_cache[cache_key] = mock_token_info

        # 设置API响应
        auth_manager.api_client.request = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                    "expires_in": 7200
                }
            }
        )

        token = await auth_manager.get_user_token(
            user_id="test_user",
            password="test_password",
            force_refresh=True
        )

        # 应该返回新Token
        assert token == "new_token"
        # 应该调用API
        auth_manager.api_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_token_expired(self, auth_manager):
        """测试Token过期时自动刷新"""
        # 设置一个即将过期的Token（已过期）
        cache_key = auth_manager._get_cache_key("test_user", "test_password")
        auth_manager._token_cache[cache_key] = TokenInfo(
            access_token="old_token",
            refresh_token="refresh",
            expires_at=time.time() - 100,  # 已过期
            user_id="test_user"
        )

        # 设置API响应
        auth_manager.api_client.request = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                    "expires_in": 7200
                }
            }
        )

        token = await auth_manager.get_user_token(
            user_id="test_user",
            password="test_password"
        )

        # 应该获取新Token
        assert token == "new_token"
        auth_manager.api_client.request.assert_called_once()


# ===========================================
# Token刷新测试
# ===========================================

class TestTokenRefresh:
    """测试Token刷新功能"""

    @pytest.mark.asyncio
    async def test_refresh_user_token(self, auth_manager):
        """测试刷新Token"""
        # 预先设置缓存
        cache_key = auth_manager._get_cache_key("test_user", "test_password")
        auth_manager._token_cache[cache_key] = TokenInfo(
            access_token="old_token",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
            user_id="test_user"
        )

        # 设置API响应
        auth_manager.api_client.request = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "access_token": "refreshed_token",
                    "refresh_token": "refreshed_refresh",
                    "expires_in": 7200
                }
            }
        )

        token = await auth_manager.refresh_user_token(
            user_id="test_user",
            password="test_password"
        )

        assert token == "refreshed_token"

        # 旧Token应该被清除
        updated_token = auth_manager._token_cache[cache_key]
        assert updated_token.access_token == "refreshed_token"


# ===========================================
# 缓存管理测试
# ===========================================

class TestCacheManagement:
    """测试缓存管理功能"""

    def test_clear_all_cache(self, auth_manager):
        """测试清除所有缓存"""
        # 添加多个Token到缓存
        auth_manager.set_token("user1", "pass1", "token1", expires_in=7200)
        auth_manager.set_token("user2", "pass2", "token2", expires_in=7200)

        assert len(auth_manager._token_cache) == 2

        auth_manager.clear_cache()

        assert len(auth_manager._token_cache) == 0

    def test_clear_specific_user_cache(self, auth_manager):
        """测试清除指定用户缓存"""
        # 添加多个Token到缓存
        auth_manager.set_token("user1", "pass1", "token1", expires_in=7200)
        auth_manager.set_token("user2", "pass2", "token2", expires_in=7200)

        assert len(auth_manager._token_cache) == 2

        # 清除user1的缓存
        auth_manager.clear_cache("user1")

        # 应该只剩user2
        stats = auth_manager.get_cache_stats()
        assert stats["total"] == 1

    def test_get_cache_stats(self, auth_manager):
        """测试获取缓存统计"""
        # 添加一些Token
        # 有效的Token
        auth_manager.set_token("user1", "pass1", "token1", expires_in=7200)
        # 过期的Token
        auth_manager.set_token("user2", "pass2", "token2", expires_in=-100)

        stats = auth_manager.get_cache_stats()

        assert stats["total"] == 2
        assert stats["valid"] >= 1
        assert stats["expired"] >= 1


# ===========================================
# Token有效性检查测试
# ===========================================

class TestTokenValidity:
    """测试Token有效性检查"""

    def test_is_token_valid_true(self, auth_manager):
        """测试有效Token"""
        auth_manager.set_token("user1", "pass1", "token1", expires_in=7200)

        result = auth_manager.is_token_valid("user1", "pass1")

        assert result is True

    def test_is_token_valid_false_not_in_cache(self, auth_manager):
        """测试Token不在缓存中"""
        result = auth_manager.is_token_valid("nonexistent", "password")

        assert result is False

    def test_is_token_valid_false_expired(self, auth_manager):
        """测试Token已过期"""
        # 设置一个即将过期的Token（在buffer时间内）
        auth_manager.set_token("user1", "pass1", "token1", expires_in=100)

        result = auth_manager.is_token_valid("user1", "pass1")

        # 由于buffer_seconds=300，100秒的token被认为是无效的
        assert result is False


# ===========================================
# Token信息获取测试
# ===========================================

class TestTokenInfo:
    """测试Token信息获取"""

    def test_get_token_info_exists(self, auth_manager):
        """测试获取存在的Token信息"""
        auth_manager.set_token(
            "user1",
            "pass1",
            "token1",
            refresh_token="refresh1",
            expires_in=7200
        )

        token_info = auth_manager.get_token_info("user1", "pass1")

        assert token_info is not None
        assert token_info.access_token == "token1"
        assert token_info.refresh_token == "refresh1"
        assert token_info.user_id == "user1"

    def test_get_token_info_not_exists(self, auth_manager):
        """测试获取不存在的Token信息"""
        token_info = auth_manager.get_token_info("nonexistent", "password")

        assert token_info is None


# ===========================================
# 手动设置Token测试
# ===========================================

class TestManualTokenSet:
    """测试手动设置Token"""

    def test_set_token_with_all_params(self, auth_manager):
        """测试设置完整Token信息"""
        auth_manager.set_token(
            "user1",
            "pass1",
            "token1",
            refresh_token="refresh1",
            expires_in=3600
        )

        token_info = auth_manager.get_token_info("user1", "pass1")

        assert token_info.access_token == "token1"
        assert token_info.refresh_token == "refresh1"
        assert token_info.user_id == "user1"
        # 验证过期时间（允许1秒误差）
        assert abs(token_info.expires_at - (time.time() + 3600)) < 2

    def test_set_token_default_expires_in(self, auth_manager):
        """测试默认过期时间"""
        auth_manager.set_token("user1", "pass1", "token1")

        token_info = auth_manager.get_token_info("user1", "pass1")

        # 默认2小时
        assert abs(token_info.expires_at - (time.time() + 7200)) < 2


# ===========================================
# 缓存Key生成测试
# ===========================================

class TestCacheKey:
    """测试缓存Key生成"""

    def test_cache_key_format(self, auth_manager):
        """测试缓存Key格式"""
        key = auth_manager._get_cache_key("test_user", "test_password")

        assert key.startswith("test_user:")
        assert len(key) > len("test_user:")

    def test_cache_key_different_passwords(self, auth_manager):
        """测试不同密码生成不同Key"""
        key1 = auth_manager._get_cache_key("user", "pass1")
        key2 = auth_manager._get_cache_key("user", "pass2")

        assert key1 != key2


# ===========================================
# 错误处理测试
# ===========================================

class TestAuthErrorHandling:
    """测试认证错误处理"""

    @pytest.mark.asyncio
    async def test_get_user_token_login_failure(self, auth_manager):
        """测试登录失败"""
        auth_manager.api_client.request = AsyncMock(
            side_effect=MeiyaApiError("登录失败", code=1001)
        )

        with pytest.raises(MeiyaApiError):
            await auth_manager.get_user_token("test_user", "wrong_password")

    @pytest.mark.asyncio
    async def test_get_user_token_missing_access_token(self, auth_manager):
        """测试响应中无access_token"""
        auth_manager.api_client.request = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    # 没有access_token
                    "refresh_token": "refresh"
                }
            }
        )

        token = await auth_manager.get_user_token("test_user", "test_password")

        # access_token为None
        assert token is None
