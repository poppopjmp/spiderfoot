#!/usr/bin/env python3
"""Generate Python gRPC stubs from proto/spiderfoot.proto.

Usage:
    python scripts/generate_proto.py

Requires: grpcio-tools, protobuf (pip install grpcio-tools protobuf)
"""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    proto_dir = root / "proto"
    out_dir = root / "spiderfoot"
    proto_file = proto_dir / "spiderfoot.proto"

    if not proto_file.exists():
        print(f"ERROR: {proto_file} not found")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        str(proto_file),
    ]

    print(f"Generating gRPC stubs from {proto_file}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: protoc failed:\n{result.stderr}")
        sys.exit(1)

    # Fix import paths in generated files (use relative imports)
    grpc_file = out_dir / "spiderfoot_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        content = content.replace(
            "import spiderfoot_pb2 as spiderfoot__pb2",
            "from spiderfoot import spiderfoot_pb2 as spiderfoot__pb2"
        )
        grpc_file.write_text(content)

    print("[OK] Generated spiderfoot/spiderfoot_pb2.py")
    print("[OK] Generated spiderfoot/spiderfoot_pb2_grpc.py")
    print("[OK] Fixed import paths for package-level imports")


if __name__ == "__main__":
    main()
