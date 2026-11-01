"""Measure total Bagron compilation time with the editable Gram dependency.

The measured interval includes ``vnma`` startup, Gram tokenization and parsing,
Bagron semantic analysis, LLVM generation, linking, and executable creation.
The compiler always uses Gram's compiled FFI driver to produce GIR in memory.
Historical Python-parser measurements remain in the changelog as reference
points; this script measures the current production path only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = _non_negative_int(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _gram_revision(gram_path: Path) -> str:
    if not gram_path.is_dir() or shutil.which("git") is None:
        return "unknown"
    result = subprocess.run(
        ["git", "-C", str(gram_path), "describe", "--tags", "--always", "--dirty"],
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and revision else "unknown"


def _compile(
    vnma: str,
    repo: Path,
    target: Path,
) -> tuple[float, int, str]:
    command = [vnma, 'run', 'main.py', str(target.relative_to(repo))]
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return elapsed, result.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure total Bagron compilation time against the editable Gram checkout."
    )
    parser.add_argument(
        "--target",
        default="examples/canon/_main.bg",
        help="Bagron source file to compile (default: examples/canon/_main.bg)",
    )
    parser.add_argument(
        "--warmup",
        type=_non_negative_int,
        default=1,
        help="Number of unreported warmup compilations (default: 1)",
    )
    parser.add_argument(
        "--samples",
        type=_positive_int,
        default=5,
        help="Number of reported compilations (default: 5)",
    )
    parser.add_argument(
        "--gram-path",
        type=Path,
        default=Path.home() / "Desktop" / "Gram",
        help="Editable Gram checkout used for revision reporting",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    target = (repo / args.target).resolve()
    if not target.is_file() or repo not in target.parents:
        parser.error(f"target must be a file inside {repo}: {target}")

    vnma = shutil.which("vnma")
    if vnma is None:
        print("vnma was not found on PATH", file=sys.stderr)
        return 1

    print(f"target={target.relative_to(repo)}")
    print(f"gram={_gram_revision(args.gram_path.resolve())}")
    print(f"warmup={args.warmup} samples={args.samples}")
    print('frontend=gram-ffi-gir')

    for warmup_index in range(args.warmup):
        _, exit_code, output = _compile(
            vnma,
            repo,
            target,
        )
        if exit_code:
            print(f"warmup={warmup_index + 1} failed with exit={exit_code}", file=sys.stderr)
            print(output, file=sys.stderr)
            return exit_code

    samples: list[float] = []
    for sample_index in range(args.samples):
        elapsed, exit_code, output = _compile(
            vnma,
            repo,
            target,
        )
        if exit_code:
            print(f"sample={sample_index + 1} failed with exit={exit_code}", file=sys.stderr)
            print(output, file=sys.stderr)
            return exit_code
        samples.append(elapsed)
        print(f"sample={sample_index + 1} seconds={elapsed:.3f} exit=0")

    ordered = sorted(samples)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2
    average = sum(samples) / len(samples)
    print("samples_seconds=" + ", ".join(f"{sample:.3f}" for sample in samples))
    print(f"min_seconds={min(samples):.3f}")
    print(f"median_seconds={median:.3f}")
    print(f"average_seconds={average:.3f}")
    print(f"max_seconds={max(samples):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
