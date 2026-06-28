"""命令行界面 — 基于 Click."""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

import click
import yaml

from . import __version__
from .models.extraction_config import ExtractionConfig
from .core.engine import ExtractionEngine
from .utils.encoding import detect_encoding
from .utils.logging import create_debug_logger

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """配置日志."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.version_option(version=__version__, prog_name="adb")
@click.option("--debug", is_flag=True, help="Enable debug logging and file log")
@click.pass_context
def main(ctx, debug):
    """Abaqus Data Bridge — 从 Abaqus .inp/.dat 中一键提取结果到 CSV."""
    ctx.ensure_object(dict)
    if debug:
        setup_logging("DEBUG")
        # --debug 同时启用文件日志
        os.environ["ADB_DEBUG_LOG"] = "1"
    else:
        setup_logging("INFO")


@main.command()
@click.option("-c", "--config", "config_file", type=click.Path(exists=True),
              help="YAML 配置文件路径")
@click.option("-i", "--inp", "inp_file", type=click.Path(exists=True),
              help="INP 输入文件路径")
@click.option("-d", "--dat", "dat_file", type=click.Path(exists=True),
              help="DAT 结果文件路径")
@click.option("-o", "--output", "output_dir", type=click.Path(),
              default="./output", help="输出目录 (默认: ./output)")
@click.option("--nsets", help="逗号分隔的节点集名称")
@click.option("--elsets", help="逗号分隔的单元集名称")
@click.option("--steps", help="逗号分隔的 Step 名称")
@click.option("--increments", default="last",
              help="Increment 筛选: last|all|1,3,5")
@click.option("--variables", default="",
              help="逗号分隔的变量类型: U,RF,S,E,CNORMF,CPRESS,COPEN,S11,SF")
@click.option("--encoding", help="文件编码 (自动检测)")
@click.option("--format", "fmt", default="csv",
              type=click.Choice(["csv", "tsv"]), help="输出格式")
@click.option("--no-metadata", is_flag=True, help="不包含元数据头部")
@click.option("--merge", is_flag=True, help="合并所有结果到一个文件")
def extract(
    config_file, inp_file, dat_file, output_dir,
    nsets, elsets, steps, increments, variables,
    encoding, fmt, no_metadata, merge
):
    """从 Abaqus 结果中提取数据并导出 CSV.

    支持 YAML 配置文件 和/或 命令行参数。

    \b
    示例:
      adb extract -c config.yaml
      adb extract -i model.inp -d results.dat -o ./out --nsets "TOP,BOTTOM"
      adb extract -i model.inp -d results.dat --variables "U,RF,S"
    """
    # --- 构建配置 ---
    if config_file:
        with open(config_file, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        config = ExtractionConfig.from_dict(yaml_data)
    else:
        config = ExtractionConfig()

    # 命令行参数覆盖配置文件
    if inp_file:
        config.inp_file = inp_file
    if dat_file:
        config.dat_file = dat_file
    if output_dir:
        config.output_dir = output_dir
    if nsets:
        config.filters.node_sets = [
            s.strip() for s in nsets.split(",") if s.strip()
        ]
    if elsets:
        config.filters.element_sets = [
            s.strip() for s in elsets.split(",") if s.strip()
        ]
    if steps:
        config.filters.steps = [
            s.strip() for s in steps.split(",") if s.strip()
        ]
    if increments:
        if increments.lower() == "last":
            config.filters.increments = "last"
        elif increments.lower() == "all":
            config.filters.increments = "all"
        else:
            try:
                config.filters.increments = [
                    int(x.strip()) for x in increments.split(",") if x.strip()
                ]
            except ValueError:
                config.filters.increments = "last"
                click.echo(f"Warning: invalid increments '{increments}', "
                           f"using 'last'", err=True)
    if variables:
        var_list = [v.strip().upper() for v in variables.split(",") if v.strip()]
        for v in var_list:
            if v in ("U", "RF"):
                if v not in config.variables.nodal:
                    config.variables.nodal.append(v)
            elif v in ("S", "E"):
                if v not in config.variables.element:
                    config.variables.element.append(v)
            elif v in ("CNORMF", "CSHEARF", "CPRESS", "COPEN", "CSLIP"):
                if v not in config.variables.contact:
                    config.variables.contact.append(v)
            elif v in ("S11", "E11"):
                if v not in config.variables.spring:
                    config.variables.spring.append(v)
            elif v in ("SF", "SM"):
                if v not in config.variables.section:
                    config.variables.section.append(v)

    if encoding:
        config.output.encoding = encoding
    if fmt == "tsv":
        config.output.format = "tsv"
        config.output.delimiter = "\t"
    if no_metadata:
        config.output.include_metadata = False
    if merge:
        config.output.merge_sets = True

    # --- 验证 ---
    if not config.inp_file or not config.dat_file:
        click.echo(
            "Error: INP and DAT files are required. "
            "Use -i/--inp and -d/--dat or -c/--config.",
            err=True
        )
        sys.exit(1)

    if not os.path.exists(config.inp_file):
        click.echo(f"Error: INP file not found: {config.inp_file}", err=True)
        sys.exit(1)
    if not os.path.exists(config.dat_file):
        click.echo(f"Error: DAT file not found: {config.dat_file}", err=True)
        sys.exit(1)

    # --- 执行 ---
    click.echo(f"ADB v{__version__}")
    click.echo(f"  INP: {config.inp_file}")
    click.echo(f"  DAT: {config.dat_file}")
    click.echo(f"  Output: {config.output_dir}")
    click.echo()

    try:
        debug_log = create_debug_logger(
            output_dir=config.output_dir,
            job_name=config.job_name,
        )
        engine = ExtractionEngine(config, debug_log=debug_log)
        stats = engine.run()
    except Exception as e:
        click.echo(f"Error during extraction: {e}", err=True)
        if "--debug" in sys.argv:
            raise
        sys.exit(1)

    # --- 输出统计 ---
    click.echo()
    click.echo("=" * 50)
    click.echo("  Extraction Complete")
    click.echo("=" * 50)
    click.echo(f"  Job:         {stats.get('job_name', 'N/A')}")
    click.echo(f"  Status:      {stats.get('analysis_status', 'N/A')}")
    click.echo(f"  Nodes:       {stats.get('node_count', 0)}")
    click.echo(f"  Elements:    {stats.get('element_count', 0)}")
    click.echo(f"  Node Sets:   {stats.get('nset_count', 0)}")
    click.echo(f"  Elem Sets:   {stats.get('elset_count', 0)}")
    click.echo(f"  Steps:       {stats.get('step_count', 0)}")
    click.echo(f"  Result Groups: {stats.get('result_groups', 0)}")
    click.echo(f"  Total Rows:  {stats.get('total_rows', 0)}")
    click.echo(f"  Files:       {stats.get('exported_files', 0)}")
    click.echo(f"  Output Dir:  {config.output_dir}")


@main.command()
@click.argument("dat_file", type=click.Path(exists=True))
@click.option("--encoding", help="文件编码 (自动检测)")
def inspect(dat_file, encoding):
    """查看 DAT 文件包含的结果信息.

    显示 Step 列表、Increment 数量、表格类型和变量。
    """
    from .parsers.dat_parser import parse_dat

    click.echo(f"Reading: {dat_file}")
    click.echo()

    try:
        debug_log = create_debug_logger(job_name=Path(dat_file).stem)
        results = parse_dat(dat_file, encoding=encoding, debug_log=debug_log)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(results.summary())

    # 详细列出所有表格
    click.echo()
    click.echo("--- Detailed Tables ---")
    for step_name, step in results.steps.items():
        for inc_num in sorted(step.increments.keys()):
            inc = step.increments[inc_num]
            click.echo(f"\n[{step_name}] Increment {inc_num} "
                       f"(Step Time: {inc.step_time:.6E})")
            for i, table in enumerate(inc.tables):
                var_str = ", ".join(table.variable_names[:8])
                if len(table.variable_names) > 8:
                    var_str += f", ... (+{len(table.variable_names) - 8})"
                click.echo(
                    f"  Table {i+1}: {table.table_type} | "
                    f"Set: {table.set_name or '(all)'} | "
                    f"Vars: [{var_str}] | "
                    f"Rows: {table.get_row_count()}"
                )
                if table.entity_type:
                    click.echo(f"    Entity Type: {table.entity_type}")


@main.command()
@click.argument("inp_file", type=click.Path(exists=True))
@click.option("--encoding", help="文件编码 (自动检测)")
@click.option("--type", "set_type", type=click.Choice(["nset", "elset", "all"]),
              default="all", help="Set 类型")
def list_sets(inp_file, encoding, set_type):
    """列出 INP 文件中定义的 Set."""
    from .parsers.inp_parser import parse_inp

    click.echo(f"Reading: {inp_file}")
    click.echo()

    try:
        model = parse_inp(inp_file, encoding=encoding)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if set_type in ("nset", "all"):
        click.echo(f"--- Node Sets ({model.get_nset_count()}) ---")
        for name in sorted(model.nsets.keys()):
            ids = model.nsets[name]
            preview = ids[:5]
            preview_str = ", ".join(str(i) for i in preview)
            if len(ids) > 5:
                preview_str += f", ... (+{len(ids) - 5})"
            click.echo(f"  {name}: [{preview_str}]")

    if set_type in ("elset", "all"):
        click.echo(f"\n--- Element Sets ({model.get_elset_count()}) ---")
        for name in sorted(model.elsets.keys()):
            ids = model.elsets[name]
            preview = ids[:5]
            preview_str = ", ".join(str(i) for i in preview)
            if len(ids) > 5:
                preview_str += f", ... (+{len(ids) - 5})"
            click.echo(f"  {name}: [{preview_str}]")


@main.command()
def wizard():
    """交互式配置向导."""
    click.echo("ADB Interactive Setup Wizard")
    click.echo("=" * 40)
    click.echo()

    # INP file
    inp_file = click.prompt("INP file path", type=click.Path(exists=True))
    dat_file = click.prompt("DAT file path", type=click.Path(exists=True))
    output_dir = click.prompt(
        "Output directory", type=click.Path(), default="./output"
    )

    click.echo()
    click.echo("Select result types to extract (comma-separated):")
    click.echo("  U=Displacement  RF=Reaction Force  S=Stress  E=Strain")
    click.echo("  CNORMF=Contact Normal Force  CPRESS=Contact Pressure")
    click.echo("  COPEN=Contact Opening  S11=Spring Force  SF=Section Force")
    click.echo("  Leave empty for ALL")
    variables = click.prompt("Variables", default="")

    click.echo()
    click.echo("Filter by sets? (comma-separated, leave empty for ALL)")
    nsets = click.prompt("Node sets", default="")
    elsets = click.prompt("Element sets", default="")

    steps = click.prompt("Steps (comma-separated, empty=ALL)", default="")
    increments = click.prompt(
        "Increments (last, all, or 1,3,5)", default="last"
    )

    # Build config
    config = ExtractionConfig()
    config.inp_file = inp_file
    config.dat_file = dat_file
    config.output_dir = output_dir

    if variables:
        var_list = [v.strip().upper() for v in variables.split(",")]
        for v in var_list:
            if v in ("U", "RF"):
                config.variables.nodal.append(v)
            elif v in ("S", "E"):
                config.variables.element.append(v)
            elif v in ("CNORMF", "CSHEARF", "CPRESS", "COPEN", "CSLIP"):
                config.variables.contact.append(v)
            elif v in ("S11", "E11"):
                config.variables.spring.append(v)
            elif v in ("SF", "SM"):
                config.variables.section.append(v)

    if nsets:
        config.filters.node_sets = [s.strip() for s in nsets.split(",")]
    if elsets:
        config.filters.element_sets = [s.strip() for s in elsets.split(",")]
    if steps:
        config.filters.steps = [s.strip() for s in steps.split(",")]
    if increments.lower() == "last":
        config.filters.increments = "last"
    elif increments.lower() == "all":
        config.filters.increments = "all"
    else:
        try:
            config.filters.increments = [
                int(x.strip()) for x in increments.split(",")
            ]
        except ValueError:
            config.filters.increments = "last"

    # Auto-detect job name
    job_name = Path(dat_file).stem
    config.job_name = job_name

    click.echo()
    click.echo("Configuration ready. Running extraction...")
    click.echo()

    try:
        debug_log = create_debug_logger(
            output_dir=config.output_dir,
            job_name=config.job_name,
        )
        engine = ExtractionEngine(config, debug_log=debug_log)
        stats = engine.run()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo()
    click.echo(f"Done! {stats.get('exported_files', 0)} files exported "
               f"to {config.output_dir}")


@main.command()
@click.argument("job_list", type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", type=click.Path(),
              default="./batch_output", help="输出根目录")
@click.option("--format", "fmt", default="csv",
              type=click.Choice(["csv", "tsv"]), help="输出格式")
def batch(job_list, output_dir, fmt):
    """批量处理多个 Job.

    JOB_LIST 是一个文本文件，每行包含: job_name inp_path dat_path

    \b
    文件格式示例:
      job1  /path/to/job1.inp  /path/to/job1.dat
      job2  /path/to/job2.inp  /path/to/job2.dat
      job3  /path/to/job3.inp  /path/to/job3.dat
    """
    from pathlib import Path

    if not os.path.exists(job_list):
        click.echo(f"Error: Job list not found: {job_list}", err=True)
        sys.exit(1)

    with open(job_list, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    if not lines:
        click.echo("Error: Job list is empty", err=True)
        sys.exit(1)

    jobs = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            jobs.append((parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            # 自动检测: job_name  →  {job_name}.inp, {job_name}.dat
            jobs.append((parts[0], f"{parts[0]}.inp", f"{parts[0]}.dat"))

    if not jobs:
        click.echo("Error: No valid job entries found", err=True)
        sys.exit(1)

    click.echo(f"Batch processing {len(jobs)} jobs...")
    click.echo()

    success_count = 0
    fail_count = 0
    total_rows = 0
    total_files = 0

    # 尝试使用进度条
    try:
        from tqdm import tqdm
        job_iter = tqdm(jobs, desc="Jobs", unit="job")
    except ImportError:
        job_iter = jobs

    for job_name, inp_path, dat_path in job_iter:
        click.echo(f"  Processing: {job_name}")

        if not os.path.exists(inp_path):
            click.echo(f"    WARNING: INP not found: {inp_path}, skipping")
            fail_count += 1
            continue
        if not os.path.exists(dat_path):
            click.echo(f"    WARNING: DAT not found: {dat_path}, skipping")
            fail_count += 1
            continue

        config = ExtractionConfig()
        config.job_name = job_name
        config.inp_file = inp_path
        config.dat_file = dat_path
        config.output_dir = os.path.join(output_dir, job_name)
        if fmt == "tsv":
            config.output.format = "tsv"
            config.output.delimiter = "\t"

        try:
            debug_log = create_debug_logger(
                output_dir=os.path.join(output_dir, job_name),
                job_name=job_name,
            )
            engine = ExtractionEngine(config, debug_log=debug_log)
            stats = engine.run()
            success_count += 1
            total_rows += stats.get("total_rows", 0)
            total_files += stats.get("exported_files", 0)
        except Exception as e:
            click.echo(f"    ERROR: {e}", err=True)
            fail_count += 1

    click.echo()
    click.echo("=" * 50)
    click.echo("  Batch Complete")
    click.echo("=" * 50)
    click.echo(f"  Success:   {success_count}")
    click.echo(f"  Failed:    {fail_count}")
    click.echo(f"  Total Rows: {total_rows}")
    click.echo(f"  Total Files: {total_files}")
    click.echo(f"  Output Dir: {output_dir}")


@main.command()
@click.argument("dat_file", type=click.Path(exists=True))
@click.option("--encoding", help="文件编码")
def stats(dat_file, encoding):
    """显示 DAT 文件中数值结果的统计信息.

    对每个变量计算 min, max, mean, std.
    """
    from .parsers.dat_parser import parse_dat
    from .core.statistics import compute_statistics, format_stats_table

    debug_log = create_debug_logger(job_name=Path(dat_file).stem)
    results = parse_dat(dat_file, encoding=encoding, debug_log=debug_log)

    if not results.steps:
        click.echo("No results found in DAT file.")
        return

    click.echo(f"Job: {results.job_name}")
    click.echo(f"Status: {results.completion_status}")
    click.echo()

    for step_name, step in results.steps.items():
        for inc_num in sorted(step.increments.keys()):
            inc = step.increments[inc_num]
            click.echo(f"[{step_name}] Increment {inc_num}")

            for table in inc.tables:
                records = table.to_records()
                if not records:
                    continue

                var_names = table.variable_names or list(
                    k for k in records[0].keys()
                    if k not in ("ENTITY_ID",)
                )
                stats_result = compute_statistics(records, var_names)
                click.echo(f"\n  {table.table_type} | {table.set_name}")
                click.echo(format_stats_table(stats_result))
                click.echo()


if __name__ == "__main__":
    main()
