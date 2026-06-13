import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

import dashboard


if __name__ == "__main__":
    dashboard.main(app_mode="user")
