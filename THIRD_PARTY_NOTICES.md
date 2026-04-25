# Third-Party Notices

This file summarises third-party software and assets redistributed with
the LBNL low-energy beta particle visualization tool.

The comprehensive dependency and attribution list is maintained in the
project wiki at
[`Licenses & Credits`](https://github.com/OSUCSVisualizationTeam/le-beta-particle-vis-lbnl/wiki/Licenses-%26-Credits).
This document highlights the items that carry redistribution obligations
or that ship as binary assets inside the wheel / PyInstaller bundle.

---

## Bundled assets

### DejaVu Fonts

- **Files:** `src/le_beta_vis/common/fonts/DejaVuSans.ttf`,
  `src/le_beta_vis/common/fonts/DejaVuSansMono.ttf`
- **Full license text:** [`src/le_beta_vis/common/fonts/LICENSE_DEJAVU`](src/le_beta_vis/common/fonts/LICENSE_DEJAVU)
- **Summary:** Bitstream Vera Fonts Copyright (permissive, MIT-style).
  Reproduction and distribution are permitted; the full license text
  must accompany any redistribution — it does, via the file above,
  which is bundled alongside the TTFs in every wheel and PyInstaller
  build.
- **Upstream:** <https://dejavu-fonts.github.io/>

---

## Runtime Python dependencies

A full table of runtime dependencies and their licenses lives in the
wiki ([`Licenses & Credits`](https://github.com/OSUCSVisualizationTeam/le-beta-particle-vis-lbnl/wiki/Licenses-%26-Credits)).
Dependencies are declared in [`pyproject.toml`](pyproject.toml).

Redistribution-notable items:

- **PySide6** — LGPL-3.0. Shipped as installed by `uv`/`pip`; no static
  linking; end users retain the right to relink against modified Qt.
- **OpenCV (opencv-python)** — Apache-2.0.
- **watchdog** — Apache-2.0.
- **mysql-connector-python** — GPL-2.0 with FOSS exception

---

## Reporting

Questions about licensing or redistribution of this project can be
directed to the OSU Visualization Team through the project's GitHub
issue tracker.
