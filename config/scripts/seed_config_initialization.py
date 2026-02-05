# A one-time initialzation step to populate the nsamespace in the ConfigurationService module
from config.ConfigurationService import ConfigurationService

DEFAULT_CONFIG = {
    # Global / Infrastructure
    "global:db:connection_string" : "mysql://localhost/mlccd_vis",
    "global:db:username" : "root",
    "global:db:password" : "root",

    "global:redis:host" : "localhost",
    "global:redis:port" : 6379,
    "global:redis:channel_events" : "events/new_class",

    "global:physics:kev_conversion" : 1.02857e-5,
    "global:physics:ped_width" : 1400,

    # GUI
    "gui:raw_analysis:default_colormap" : "viridis",
    "gui:raw_analysis:vis_range_min" : 0.0,
    "gui:raw_analysis:vis_range_max" : 20.0,
    "gui:raw_analysis:filter_gaussian_sigma" : 1.5,
    "gui:raw_analysis:clustering_threshold" : 4.0,

    "gui:window:default_width" : 1024,
    "gui:window:default_height" : 700,

    "gui:mosaic:height" : 130,
    "gui:mosaic:thumbnail_height" : 100,
    "gui:mosaic:scaling_function" : "log",

    "gui:historical:default_query_hours" : 24,
    "gui:historical:live_update_rate_ms" : 1000,
    "gui:historical:mode" : "historical",

    "gui:inspector:histogram_bins" : 50, 

    "gui:export:default_path" : "~/Data",
    "gui:export:image_format" : "png",

    # Pipeline
    "pipeline:ingress:polling_location" : "~/Google Drive/My Drive/FITS"
}

# Since Redis only takes string forms, bools need to be converted as it does not serialize well automatically
def serialize_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

def seed_defaults():
    service = ConfigurationService()

    print("Connecting to Redis...")
    if not service.ping():
        raise RuntimeError("Could not connect to Redis")

    print("Seeding default configuration values...")

    for key, value in DEFAULT_CONFIG.items():
        serialized = serialize_value(value)

        service.set(key, serialized)
        print(f"SET {key} = {serialized}")

    print("Configuration seeding complete.")


if __name__ == "__main__":
    seed_defaults()