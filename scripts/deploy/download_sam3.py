#!/usr/bin/env python
"""Resumable downloader for the SAM3 checkpoint from the ModelScope mirror.

Usage:
    python download_sam3.py [--target /path/to/sam3.pt]

The HF repo facebook/sam3 is gated (403 even with a token on the mirror), so
we pull the weight file from ModelScope, which mirrors it without auth.
The download resumes from any existing partial file.
"""
import argparse
import os
import sys

import requests

URL = "https://modelscope.cn/models/facebook/sam3/resolve/master/sam3.pt"
EXPECTED = 3450062241  # bytes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.path.join(
        os.environ.get("DATA_DIR", os.path.expanduser("~")), "rpent_data",
        "checkpoints", "sam3", "sam3.pt"))
    args = ap.parse_args()
    target = args.target

    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".incomplete"

    header = {}
    if os.path.exists(tmp):
        have = os.path.getsize(tmp)
        if have >= EXPECTED:
            os.rename(tmp, target)
            print(f"already complete: {target}")
            return 0
        header["Range"] = f"bytes={have}-"
        print(f"resuming from {have} bytes")

    print(f"downloading {URL}")
    r = requests.get(URL, headers=header, stream=True, timeout=60)
    if r.status_code not in (200, 206):
        print(f"ERROR: HTTP {r.status_code} {r.text[:200]}")
        return 1

    with open(tmp, "ab") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    size = os.path.getsize(tmp)
    if size != EXPECTED:
        print(f"ERROR: size mismatch, got {size}, expected {EXPECTED}")
        return 1

    os.rename(tmp, target)
    print(f"DONE: {target} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
