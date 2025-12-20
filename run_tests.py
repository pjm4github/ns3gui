#!/usr/bin/env python3
"""
Test runner for ns-3 GUI application.

Usage:
    python run_tests.py              # Run unit + integration tests (no slow/e2e)
    python run_tests.py unit         # Run unit tests only
    python run_tests.py integration  # Run integration tests only
    python run_tests.py e2e          # Run end-to-end tests (requires ns-3)
    python run_tests.py all          # Run ALL tests including slow/e2e
    python run_tests.py --slow       # Include slow tests in any suite
    python run_tests.py --coverage   # Run with coverage report

Examples:
    python run_tests.py                    # Quick: unit + integration
    python run_tests.py e2e --slow         # E2E tests with ns-3 simulation
    python run_tests.py all --slow         # Everything including ns-3 tests
    python run_tests.py unit -v            # Verbose unit tests
    python run_tests.py --coverage         # With coverage report
"""

import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Run ns-3 GUI tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Suites:
  unit         Unit tests (fast, no dependencies)
  integration  Integration tests (may use filesystem)
  e2e          End-to-end tests (requires ns-3 installation)
  all          All test suites

Slow Tests:
  Tests marked @pytest.mark.slow (including e2e simulation tests)
  are skipped by default. Use --slow to include them.

ns-3 Configuration:
  E2E tests use the ns-3 path from Settings or auto-detect.
  Configure via the GUI: Simulation → Configure ns-3 Path
        """
    )
    parser.add_argument(
        "suite", 
        nargs="?", 
        choices=["unit", "integration", "e2e", "all"],
        default="default",
        help="Test suite to run (default: unit + integration)"
    )
    parser.add_argument(
        "--slow", 
        action="store_true",
        help="Include slow tests (required for e2e ns-3 simulation tests)"
    )
    parser.add_argument(
        "--coverage", "--cov",
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
    parser.add_argument(
        "--show-ns3",
        action="store_true",
        help="Show ns-3 detection status and exit"
    )
    
    args = parser.parse_args()
    
    # Show ns-3 status if requested
    if args.show_ns3:
        return show_ns3_status()
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Select test directory based on suite
    if args.suite == "unit":
        cmd.append("tests/unit")
    elif args.suite == "integration":
        cmd.append("tests/integration")
    elif args.suite == "e2e":
        cmd.append("tests/e2e")
        # E2E tests are slow by nature, auto-enable --slow
        if not args.slow:
            print("Note: E2E tests require --slow flag, enabling automatically")
            args.slow = True
    elif args.suite == "all":
        cmd.append("tests")
    else:
        # Default: run unit and integration but not e2e
        cmd.extend(["tests/unit", "tests/integration"])
    
    # Add verbose flag
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-v")  # Always use -v for better output
    
    # Add failfast
    if args.failfast:
        cmd.append("-x")
    
    # Handle slow tests - use --run-slow flag (defined in conftest.py)
    if args.slow:
        cmd.append("--run-slow")
    
    # Add coverage options
    if args.coverage:
        cmd.extend([
            "--cov=models",
            "--cov=services", 
            "--cov-report=term-missing",
            "--cov-report=html:coverage_report"
        ])
    
    # Print command
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    
    # Run tests
    result = subprocess.run(cmd)
    
    # Print summary for e2e tests
    if args.suite == "e2e" and result.returncode != 0:
        print("\n" + "-" * 60)
        print("E2E Test Troubleshooting:")
        print("  - Ensure ns-3 is installed and built with Python bindings")
        print("  - On Windows: ns-3 must be in WSL")
        print("  - Configure path: python run_tests.py --show-ns3")
        print("  - Or use GUI: Simulation → Configure ns-3 Path")
    
    return result.returncode


def show_ns3_status():
    """Show ns-3 detection status."""
    print("ns-3 Detection Status")
    print("=" * 60)
    
    try:
        # Try to import and use NS3Detector
        sys.path.insert(0, ".")
        from services.simulation_runner import NS3Detector, is_windows, is_wsl_available
        from services.settings_manager import get_settings
        
        # Check settings
        print("\n1. Settings File:")
        try:
            settings = get_settings()
            print(f"   Path from settings: {settings.ns3_path or '(not set)'}")
            print(f"   Use WSL: {settings.ns3_use_wsl}")
            print(f"   WSL Distribution: {settings.wsl_distribution}")
            
            if settings.ns3_path:
                valid = NS3Detector.validate_ns3_path(
                    settings.ns3_path, 
                    use_wsl=settings.ns3_use_wsl
                )
                print(f"   Valid: {valid}")
        except Exception as e:
            print(f"   Error reading settings: {e}")
        
        # Check auto-detection
        print("\n2. Auto-Detection:")
        print(f"   Platform: {'Windows' if is_windows() else 'Linux/macOS'}")
        if is_windows():
            print(f"   WSL Available: {is_wsl_available()}")
        
        detected = NS3Detector.find_ns3_path(check_wsl=True)
        if detected:
            print(f"   Detected path: {detected}")
            version = NS3Detector.get_ns3_version(detected)
            print(f"   Version: {version or 'unknown'}")
        else:
            print("   No ns-3 installation detected")
            print("\n   Common paths searched:")
            for path in NS3Detector.COMMON_PATHS[:5]:
                print(f"     - {path}")
        
        print("\n3. Configuration:")
        if detected or (settings.ns3_path and valid):
            print("   ✓ ns-3 is configured and ready for e2e tests")
            print("   Run: python run_tests.py e2e --slow")
        else:
            print("   ✗ ns-3 not found")
            print("   Install ns-3 or configure path in Settings")
        
    except ImportError as e:
        print(f"   Error importing modules: {e}")
        print("   Run from project root directory")
    
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
