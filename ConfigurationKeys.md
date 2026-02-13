# Configuration Keys

This document serves as the authoritative registry for all configuration keys used in the application. It maps the namespace, key name, expected values, and purpose of each setting managed by the Configuration Service.

| Namespace | Key | Type | Default Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| **global:db** | `connection_string` | String | `mysql://localhost/le_beta_vis` | Database connection URI for the Event Persistence Service. |
| **global:redis** | `host` | String | `localhost` | Hostname of the Redis server used for Pub/Sub messaging. |
| **global:redis** | `port` | Integer | `6379` | Port number of the Redis server. |
| **global:redis** | `channel_events` | String | `events/new_class` | Redis channel name for broadcasting new classification events. |
| **global:physics** | `kev_conversion` | Float | `1.02857e-5` | Constant factor to convert raw charge values (ADU) to energy (keV). Depends on sensor hardware. |
| **gui:raw_analysis** | `default_colormap` | String | `viridis` | Initial colormap applied when opening a new FITS file. Supported: `viridis`, `plasma`, `inferno`, `magma`, `jet`, `bone`, `hot`, `cool`. |
| **gui:raw_analysis** | `vis_range_min` | Float | `0.0` | Lower bound (in keV) for visualization thresholding. Values below this are clipped. Shared by Main View and Mosaic View. |
| **gui:raw_analysis** | `vis_range_max` | Float | `20.0` | Upper bound (in keV) for visualization thresholding. Values above this are clipped or normalized. Shared by Main View and Mosaic View. |
| **gui:raw_analysis** | `filter_gaussian_sigma` | Float | `1.5` | Sigma (radius) value for the interactive Gaussian blur filter. |
| **gui:raw_analysis** | `clustering_threshold` | Float | `4.0` | Signal-to-noise ratio (sigma multiplier) used for identifying event clusters. |
| **gui:raw_analysis** | `zoom_step_factor` | Float | `1.2` | Factor to multiply/divide scale by when zooming in or out. |
| **gui:raw_analysis** | `magnifier_display_size` | Integer | `127` | Fixed side length (in pixels) of the square magnifier overlay. |
| **gui:raw_analysis** | `magnifier_default_factor` | Float | `3.0` | Initial magnification factor when the magnifier tool is activated. |
| **gui:raw_analysis** | `magnifier_min_factor` | Float | `1.0` | Minimum allowed magnification factor for the magnifier tool. |
| **gui:raw_analysis** | `magnifier_max_factor` | Float | `100.0` | Maximum allowed magnification factor for the magnifier tool. |
| **gui:raw_analysis** | `magnifier_factor_step` | Float | `0.5` | Increment/decrement step when adjusting magnification via scroll wheel or keyboard. |
| **gui:raw_analysis** | `magnifier_move_step` | Integer | `1` | Pixel step size when moving the magnifier with arrow keys. |
| **gui:raw_analysis** | `show_tool_hints` | Boolean | `true` | Show inline usage hints on interactive tools (e.g., magnifier keyboard shortcuts). |
| **gui:window** | `default_width` | Integer | `1024` | Default initial width of the application window. |
| **gui:window** | `default_height` | Integer | `700` | Default initial height of the application window. |
| **gui:mosaic** | `height` | Integer | `130` | Fixed height (in pixels) of the Mosaic View container strip. |
| **gui:mosaic** | `thumbnail_height` | Integer | `100` | Height (in pixels) of the individual thumbnail images inside the strip. Width is calculated dynamically. |
| **gui:mosaic** | `scaling_function` | Enum (Str) | `log` | Transfer function used to render thumbnails. Values: `linear`, `log`, `sqrt`. |
| **gui:historical** | `default_query_hours` | Integer | `24` | Default lookback period (in hours) when opening the Historical Analysis view. |
| **gui:historical** | `live_update_rate_ms` | Integer | `1000` | Refresh rate (in milliseconds) for the live monitoring dashboard. |
| **gui:historical** | `mode` | Enum (Str) | `historical` | Operational mode of the Historical View. Values: `live`, `historical`. |
| **gui:inspector** | `histogram_bins` | Integer | `50` | Number of bins to use when generating energy distribution histograms for selected events. |
| **gui:export** | `default_path` | String | `~/Data` | Default file system path presented in the "Save As" dialog. |
| **gui:export** | `image_format` | String | `png` | Preferred file format for exporting plots and images. |
