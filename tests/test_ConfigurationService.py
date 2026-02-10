from le_beta_vis.common.ConfigurationService import MockConfigurationService


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
