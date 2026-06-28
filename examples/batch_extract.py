#!/usr/bin/env python3
"""示例 4: 批量提取多个 Job 的结果.

演示 Python API 批量处理。
"""

import os
from pathlib import Path
from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig


def batch_extract(job_dir: str, output_root: str):
    """批量提取目录中所有 .dat 文件的结果.

    Args:
        job_dir: 包含 .inp 和 .dat 文件的目录
        output_root: 输出根目录
    """
    dat_files = list(Path(job_dir).glob("*.dat"))
    print(f"Found {len(dat_files)} DAT files")

    results_summary = []

    for dat_path in dat_files:
        job_name = dat_path.stem
        inp_path = dat_path.with_suffix(".inp")

        if not inp_path.exists():
            print(f"  SKIP {job_name}: no matching INP file")
            continue

        config = ExtractionConfig()
        config.job_name = job_name
        config.inp_file = str(inp_path)
        config.dat_file = str(dat_path)
        config.output_dir = os.path.join(output_root, job_name)

        print(f"  Processing {job_name}...")
        try:
            engine = ExtractionEngine(config)
            stats = engine.run()
            results_summary.append({
                "job": job_name,
                "status": stats["analysis_status"],
                "nodes": stats["node_count"],
                "rows": stats["total_rows"],
                "files": stats["exported_files"],
            })
            print(f"    ✓ {stats['total_rows']} rows in "
                  f"{stats['exported_files']} files")
        except Exception as e:
            print(f"    ✗ Error: {e}")
            results_summary.append({
                "job": job_name,
                "status": "ERROR",
                "error": str(e),
            })

    # 打印汇总
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY")
    print("=" * 60)
    total_rows = sum(r.get("rows", 0) for r in results_summary)
    total_files = sum(r.get("files", 0) for r in results_summary)
    print(f"  Jobs processed: {len(results_summary)}")
    print(f"  Total rows:     {total_rows}")
    print(f"  Total files:    {total_files}")


if __name__ == "__main__":
    import sys
    job_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    output = sys.argv[2] if len(sys.argv) > 2 else "./batch_output"
    batch_extract(job_dir, output)
