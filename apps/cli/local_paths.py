import os
from pathlib import Path


def local_data_dir() -> Path:
    return Path(
        os.environ.get("LINKEDIN_DATA_DIR", Path.home() / ".linkedin-cli")
    ).expanduser()
