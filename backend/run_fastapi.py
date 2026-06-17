import logging
import os

import uvicorn

from app.config import Settings


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    uvicorn.run(
        "app.fastapi_app:app",
        host=os.getenv("FASTAPI_HOST", "127.0.0.1"),
        port=int(os.getenv("FASTAPI_PORT", "8000")),
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
