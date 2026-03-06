"""The SpiderFoot CLI has been consolidated into a single Go binary.

Build it with:  cd cli && make build
Or download from: https://github.com/smicallef/spiderfoot/releases
"""

import sys


def main() -> None:
    print(
        "The Python CLI has been replaced by a cross-platform Go binary.\n"
        "Build it with:  cd cli && make build\n"
        "Or download from: https://github.com/smicallef/spiderfoot/releases",
        file=sys.stderr,
    )
    raise SystemExit(1)


main()
