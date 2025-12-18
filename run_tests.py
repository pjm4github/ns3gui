#!/usr/bin/env python3
"""
Test runner for ns-3 GUI application.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py unit         # Run unit tests only
    python run_tests.py integration  # Run integration tests only
    python run_tests.py e2e          # Run end-to-end tests (requires ns-3)
    python run_tests.py --slow       # Include slow tests
    python run_tests.py --coverage   # Run with coverage report
"""

import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description="Run ns-3 GUI tests")
    parser.add_argument(
        "suite", 
        nargs="?", 
        choices=["unit", "integration", "e2e", "all"],
        default="all",
        help="Test suite to run"
    )
    parser.add_argument(
        "--slow", 
        action="store_true",
        help="Include slow tests"
    )
    parser.add_argument(
        "--coverage", 
        action="store_true",
        help="Run with coverage report"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--failfast", "-x",
        action="store_true",
        help="Stop on first failure"
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Select test directory
    if args.suite == "unit":
        cmd.append("tests/unit")
    elif args.suite == "integration":
        cmd.append("tests/integration")
    elif args.suite == "e2e":
        cmd.append("tests/e2e")
    else:
        cmd.append("tests")
    
    # Add options
    if args.verbose:
        cmd.append("-v")
    
    if args.failfast:
        cmd.append("-x")
    
    if not args.slow:
        cmd.extend(["-m", "not slow"])
    
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing", "--cov-report=html"])
    
    # Run tests
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
