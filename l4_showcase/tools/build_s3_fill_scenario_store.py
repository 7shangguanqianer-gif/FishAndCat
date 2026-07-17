"""情景对照 store 打包(治理 C2):把独立情景数据门投影为 src/s3_fill_store_<scenario>.js。

零改动复用 build_s3_fill_frontend_bundle 的公开函数(build_payload 走独立重放
validator 闸门,render_bundle 沿用同一队列信封渲染),生产 skew 管线与其
write_bundle 输出硬闸均不受影响。页面按 URL 参数选择加载哪一个 store,
runtime 的单 payload 队列契约保持不变。

用法(项目根):
    PYTHONIOENCODING=utf-8 python l4_showcase/tools/build_s3_fill_scenario_store.py --scenario uniform
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "l4_showcase" / "tools"))
sys.path.insert(0, str(ROOT / "sim"))

import fill_only as fill  # noqa: E402
import build_s3_fill_frontend_bundle as bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", required=True, choices=("uniform", "heavy"))
    args = parser.parse_args()

    gate_dir = ROOT / "l4_showcase" / "out" / f"s3_fill_data_gate_{args.scenario}"
    registry = ROOT / "l4_showcase" / "evidence" / f"s3_fill_release_registry_{args.scenario}.json"
    output = ROOT / "l4_showcase" / "src" / f"s3_fill_store_{args.scenario}.js"

    payload, report = bundle.build_payload(gate_dir, registry)
    rendered = bundle.render_bundle(payload)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(
        f"S3 fill {args.scenario} scenario store PASS; "
        f"release={payload['release']['release_id']}; "
        f"payload_sha256={payload['bundle_payload_sha256']}; "
        f"file_sha256={fill.file_sha256(output)}; "
        f"validator_sha256={report['report_payload_sha256']}; "
        f"output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
