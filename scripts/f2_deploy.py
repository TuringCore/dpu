#!/usr/bin/env python3
"""Minimal AWS EC2 F2 helper for the DPU repo.

This script is intentionally narrow: it prepares a manifest for a generated FPGA
bitstream and prints the AWS CLI commands needed to register the AFI and launch a
host instance. It does not replace the vendor FPGA synthesis flow.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


def cmd_prepare(args: argparse.Namespace) -> int:
    bitstream = Path(args.bitstream)
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    if not bitstream.exists():
        raise FileNotFoundError(f"bitstream not found: {bitstream}")
    manifest = {
        "bitstream": str(bitstream),
        "output_dir": str(outdir),
        "bucket": args.bucket,
        "prefix": args.prefix,
        "created_by": "dpu-f2-deploy",
    }
    package = outdir / "f2_bitstream_manifest.json"
    package.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared manifest: {package}")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    cmd = (
        "aws ec2 create-fpga-image "
        "--input-storage-location Bucket={bucket},Key={prefix}/bitstream.bin "
        "--logs-storage-location Bucket={bucket},Key={prefix}/logs "
        "--name {name} "
        "--description {description} "
        "--region {region}"
    ).format(
        bucket=args.bucket,
        prefix=args.prefix,
        name=args.name,
        description=shlex.quote(args.description),
        region=args.region,
    )
    print(cmd)
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    cmd = (
        "aws ec2 run-instances "
        "--instance-type {instance_type} "
        "--image-id {ami} "
        "--key-name {key_name} "
        "--security-group-ids {security_group}"
    ).format(
        instance_type=args.instance_type,
        ami=args.ami,
        key_name=args.key_name,
        security_group=args.security_group,
    )
    print(cmd)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Minimal AWS EC2 F2 helper for the DPU repo")
    sub = p.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Prepare a manifest for a generated FPGA bitstream")
    prepare.add_argument("--bitstream", required=True)
    prepare.add_argument("--output-dir", default="build/f2")
    prepare.add_argument("--bucket", default="")
    prepare.add_argument("--prefix", default="dpu/f2")
    prepare.set_defaults(func=cmd_prepare)

    register = sub.add_parser("register", help="Print the AFI registration command")
    register.add_argument("--bucket", required=True)
    register.add_argument("--prefix", required=True)
    register.add_argument("--name", required=True)
    register.add_argument("--description", default="DPU FPGA image")
    register.add_argument("--region", default="us-east-1")
    register.set_defaults(func=cmd_register)

    launch = sub.add_parser("launch", help="Print the EC2 launch command")
    launch.add_argument("--instance-type", default="f2")
    launch.add_argument("--ami", required=True)
    launch.add_argument("--key-name", required=True)
    launch.add_argument("--security-group", required=True)
    launch.set_defaults(func=cmd_launch)

    args = p.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

