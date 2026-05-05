import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from dashboard import main


main()
