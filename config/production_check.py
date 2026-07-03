"""Exit non-zero unless production configuration is complete and valid."""

import os
import sys

from pydantic import ValidationError

from app.core.config import Settings


def main() -> int:
    os.environ["APP_ENV"] = "production"
    try:
        Settings()
    except ValidationError as exc:
        print(f"Production configuration invalid:\n{exc}", file=sys.stderr)
        return 1
    print("Production configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

