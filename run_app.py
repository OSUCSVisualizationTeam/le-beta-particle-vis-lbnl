import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from le_beta_vis.app import main  # noqa: E402

if __name__ == "__main__":
    main()
