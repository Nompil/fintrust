"""Resource root for the repository source layout and the Lambda archive layout."""
from pathlib import Path
PACKAGE_PARENT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = PACKAGE_PARENT.parent if PACKAGE_PARENT.name == "backend" else PACKAGE_PARENT
