import os
import pytest
import redis

from config.ConfigurationService import ConfigurationService
from config.scripts.seed_config_initialization import DEFAULT_CONFIG, seed_defaults, serialize_value


TEST_DB = 15  # isolated DB index for tests


def _redis_available() -> bool:
    password = os.getenv("REDIS_PASSWORD")
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379"))

    if not password:
        return False

    try:
        client = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=TEST_DB,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        return bool(client.ping())
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _skip_if_no_redis():
    if not _redis_available():
        pytest.skip("Redis not available. Start Redis and set REDIS_PASSWORD to run these tests.")


@pytest.fixture
def redis_client():
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD")

    client = redis.Redis(
        host=host,
        port=port,
        password=password,
        db=TEST_DB,
        decode_responses=True,
    )

    # Clean DB before each test so tests are independent
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def service(redis_client, monkeypatch):
    # Patch redis.Redis constructor used inside ConfigurationService to always use db=TEST_DB
    original_redis = redis.Redis

    def redis_with_test_db(*args, **kwargs):
        kwargs["db"] = TEST_DB
        kwargs["decode_responses"] = True
        return original_redis(*args, **kwargs)

    monkeypatch.setattr(redis, "Redis", redis_with_test_db)

    svc = ConfigurationService()
    assert svc.ping() is True
    return svc


def test_configuration_service_set_get(service):
    key = "gui:test:key"
    value = "12345"

    assert service.get(key) is None
    service.set(key, value)
    assert service.get(key) == value


def test_seed_defaults_populates_all_keys(service):
    # Ensure empty before seeding
    for key in DEFAULT_CONFIG.keys():
        assert service.get(key) is None

    # Run seeding routine
    seed_defaults()

    # Verify every key exists and equals the expected serialized value
    for key, expected in DEFAULT_CONFIG.items():
        stored = service.get(key)
        assert stored is not None, f"Missing key after seeding: {key}"
        assert stored == serialize_value(expected), f"Value mismatch for {key}"


def test_seed_defaults_idempotent(service):
    seed_defaults()
    seed_defaults()

    for key, expected in DEFAULT_CONFIG.items():
        assert service.get(key) == serialize_value(expected)


def test_required_keys_exist_after_seeding(service):
    seed_defaults()

    assert service.get("global:db:connection_string") == serialize_value("mysql://localhost/mlccd_vis")
    assert service.get("global:physics:kev_conversion") == serialize_value(1.02857e-5)
    assert service.get("gui:raw_analysis:default_colormap") == serialize_value("viridis")
    assert service.get("gui:raw_analysis:vis_range_min") == serialize_value(0.0)
