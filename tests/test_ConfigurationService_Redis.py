import pytest
from unittest.mock import MagicMock, patch
from le_beta_vis.common.RedisBackedConfigurationService import RedisBackedConfigurationService


@pytest.fixture(autouse=True)
def redis_env(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "test-password")
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "6379")


@patch("le_beta_vis.common.RedisBackedConfigurationService.load_dotenv")
@patch("le_beta_vis.common.RedisBackedConfigurationService.redis.Redis")
def test_get_returns_default_when_key_missing(mock_redis, mock_dotenv):
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_redis.return_value = mock_client

    service = RedisBackedConfigurationService()
    assert service.get("gui:raw_analysis:vis_range_min", 0.0) == 0.0


@patch("le_beta_vis.common.RedisBackedConfigurationService.load_dotenv")
@patch("le_beta_vis.common.RedisBackedConfigurationService.redis.Redis")
def test_get_coerces_float(mock_redis, mock_dotenv):
    mock_client = MagicMock()
    mock_client.get.return_value = "1.5"
    mock_redis.return_value = mock_client

    service = RedisBackedConfigurationService()
    result = service.get("gui:raw_analysis:filter_gaussian_sigma")
    assert result == 1.5
    assert isinstance(result, float)


@patch("le_beta_vis.common.RedisBackedConfigurationService.load_dotenv")
@patch("le_beta_vis.common.RedisBackedConfigurationService.redis.Redis")
def test_get_coerces_int(mock_redis, mock_dotenv):
    mock_client = MagicMock()
    mock_client.get.return_value = "6379"
    mock_redis.return_value = mock_client

    service = RedisBackedConfigurationService()
    result = service.get("global:redis:port")
    assert result == 6379
    assert isinstance(result, int)


@patch("le_beta_vis.common.RedisBackedConfigurationService.load_dotenv")
@patch("le_beta_vis.common.RedisBackedConfigurationService.redis.Redis")
def test_set_serializes_bool(mock_redis, mock_dotenv):
    mock_client = MagicMock()
    mock_redis.return_value = mock_client

    service = RedisBackedConfigurationService()
    service.set("some:bool:key", True)
    mock_client.set.assert_called_once_with("some:bool:key", "true")