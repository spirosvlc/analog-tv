import uvicorn

from analog_tv.application import ApplicationFactory
from analog_tv.core.config import get_settings

app = ApplicationFactory.create()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "analog_tv.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
