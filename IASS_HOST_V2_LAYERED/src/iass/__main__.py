import argparse
import os

import uvicorn

from iass.api.app import create_app


def main():
    parser = argparse.ArgumentParser(description="IASS Host V1")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--ssl-keyfile", default=os.environ.get("IASS_SSL_KEYFILE"))
    parser.add_argument("--ssl-certfile", default=os.environ.get("IASS_SSL_CERTFILE"))
    args = parser.parse_args()
    debug = os.environ.get("IASS_START_MODE") == "debug"
    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="debug" if debug else "info",
        ssl_keyfile=args.ssl_keyfile or None,
        ssl_certfile=args.ssl_certfile or None,
    )


if __name__ == "__main__":
    main()
