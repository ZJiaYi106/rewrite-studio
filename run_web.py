from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    import config

    uvicorn.run("web.app:app", host=config.WEB_HOST, port=config.WEB_PORT, reload=False, workers=1)
