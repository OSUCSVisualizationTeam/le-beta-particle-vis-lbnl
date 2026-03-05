#
# LEGACY CONFIGURATION SEEDING INFRASTRUCTURE, NO LONGER USED
#
import yaml
from pathlib import Path
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.RedisBackedConfigurationService import (
    RedisBackedConfigurationService,
)

_DEFAULTS_PATH = Path(__file__).parent / "defaults.yaml"


def seed_defaults(service: ConfigurationService | None = None, force: bool = False):
    """
    Seed Redis with the authoritative default configuration values.

    Args:
        service: Optional pre-configured service instance for testing.
                 If None, a new RedisBackedConfigurationService is instantiated.
        force:   If True, overwrites existing keys. If False (default),
                 skips keys that already exist to prevent accidental data loss.
    """
    if service is None:
        service = RedisBackedConfigurationService()

    print("Connecting to Redis...")
    if not service.ping():
        raise RuntimeError("Could not connect to Redis")

    with open(_DEFAULTS_PATH, "r") as f:
        defaults = yaml.safe_load(f)

    print(f"Seeding default configuration values (force={force})...")
    set_count, skipped_count = 0, 0

    for key, value in defaults.items():
        if not force and service.get(key) is not None:
            print(f"  SKIP {key} (already set)")
            skipped_count += 1
        else:
            service.set(key, value)
            print(f"  SET  {key} = {value!r}")
            set_count += 1

    print(f"Done. {set_count} keys set, {skipped_count} skipped.")


if __name__ == "__main__":
    seed_defaults(force=True)
