from mock_configuration_service import MockConfigurationService


def test_mock_configuration_service_defaults():
    """Test that the mock service returns the expected default values from the design doc."""
    service = MockConfigurationService()

    # Test Global
    assert service.get("global:db:connection_string") == "mysql://localhost/mlccd_viz"

    # Test Physics
    assert service.get("global:physics:kev_conversion") == 1.02857e-5

    # Test GUI defaults
    assert service.get("gui:raw_analysis:default_colormap") == "viridis"
    assert service.get("gui:raw_analysis:vis_range_min") == 0.0
    assert service.get("gui:raw_analysis:zoom_step_factor") == 1.2


def test_mock_configuration_service_set_get():
    """Test setting and getting a new value."""
    service = MockConfigurationService()

    key = "gui:test:key"
    value = 12345

    # Ensure it's not there initially (or returns None/Default)
    assert service.get(key) is None

    # Set value
    service.set(key, value)

    # Get value
    assert service.get(key) == value


def test_mock_configuration_service_get_description_returns_none():
    """get_description() always returns None for the mock."""
    service = MockConfigurationService()
    assert service.get_description("gui:raw_analysis:default_colormap") is None
    assert service.get_description("nonexistent:key") is None


# --- Typed Getters ---


class TestTypedGetters:
    """Tests for get_int, get_float, and get_bool on ConfigurationService."""

    def _make_service(self, overrides=None):
        svc = MockConfigurationService()
        if overrides:
            for k, v in overrides.items():
                svc.set(k, v)
        return svc

    # -- get_int --

    def test_get_int_returns_int(self):
        svc = self._make_service({"k": 7})
        assert svc.get_int("k", 0) == 7
        assert isinstance(svc.get_int("k", 0), int)

    def test_get_int_uses_default_when_missing(self):
        svc = self._make_service()
        assert svc.get_int("missing:key", 42) == 42

    def test_get_int_coerces_float_to_int(self):
        svc = self._make_service({"k": 3.9})
        assert svc.get_int("k", 0) == 3

    def test_get_int_coerces_string_to_int(self):
        svc = self._make_service({"k": "10"})
        assert svc.get_int("k", 0) == 10

    def test_get_int_minimum_clamps_below(self):
        svc = self._make_service({"k": 1})
        assert svc.get_int("k", 0, minimum=5) == 5

    def test_get_int_minimum_passes_above(self):
        svc = self._make_service({"k": 10})
        assert svc.get_int("k", 0, minimum=5) == 10

    def test_get_int_maximum_clamps_above(self):
        svc = self._make_service({"k": 100})
        assert svc.get_int("k", 0, maximum=50) == 50

    def test_get_int_maximum_passes_below(self):
        svc = self._make_service({"k": 10})
        assert svc.get_int("k", 0, maximum=50) == 10

    def test_get_int_minimum_and_maximum(self):
        svc = self._make_service({"k": 1})
        assert svc.get_int("k", 0, minimum=5, maximum=20) == 5
        svc.set("k", 100)
        assert svc.get_int("k", 0, minimum=5, maximum=20) == 20
        svc.set("k", 10)
        assert svc.get_int("k", 0, minimum=5, maximum=20) == 10

    # -- get_float --

    def test_get_float_returns_float(self):
        svc = self._make_service({"k": 2.5})
        assert svc.get_float("k", 0.0) == 2.5
        assert isinstance(svc.get_float("k", 0.0), float)

    def test_get_float_uses_default_when_missing(self):
        svc = self._make_service()
        assert svc.get_float("missing:key", 0.75) == 0.75

    def test_get_float_minimum_clamps(self):
        svc = self._make_service({"k": 0.01})
        assert svc.get_float("k", 0.0, minimum=0.1) == 0.1

    # -- get_bool --

    def test_get_bool_true(self):
        svc = self._make_service({"k": True})
        assert svc.get_bool("k", False) is True

    def test_get_bool_false(self):
        svc = self._make_service({"k": False})
        assert svc.get_bool("k", True) is False

    def test_get_bool_uses_default_when_missing(self):
        svc = self._make_service()
        assert svc.get_bool("missing:key", True) is True
        assert svc.get_bool("missing:key2", False) is False
