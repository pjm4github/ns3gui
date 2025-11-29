"""
NS-3 Simulation Runner.

Manages ns-3 subprocess execution and output capture.
Supports both native Linux/macOS and Windows WSL execution.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QTimer


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_wsl_available() -> bool:
    """Check if WSL is available on Windows."""
    if not is_windows():
        return False
    try:
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def windows_to_wsl_path(win_path: str) -> str:
    """
    Convert Windows path to WSL path.
    
    C:\\Users\\Name\\folder -> /mnt/c/Users/Name/folder
    """
    path = win_path.replace('\\', '/')
    if len(path) >= 2 and path[1] == ':':
        drive = path[0].lower()
        path = f"/mnt/{drive}{path[2:]}"
    return path


def wsl_to_windows_path(wsl_path: str) -> str:
    """
    Convert WSL path to Windows path.
    
    /mnt/c/Users/Name/folder -> C:\\Users\\Name\\folder
    """
    if wsl_path.startswith('/mnt/') and len(wsl_path) > 6:
        drive = wsl_path[5].upper()
        rest = wsl_path[6:].replace('/', '\\')
        return f"{drive}:{rest}"
    return wsl_path


class NS3Detector:
    """
    Auto-detect ns-3 installation.
    
    Searches common locations and validates the installation.
    Supports both native paths and WSL paths on Windows.
    """
    
    COMMON_PATHS = [
        # User home directory
        "~/ns-3-dev",
        "~/ns-allinone-3.*/ns-3.*",
        "~/ns3",
        "~/workspace/ns-3*",
        # System paths
        "/opt/ns-3*",
        "/usr/local/ns-3*",
        # Current directory
        "./ns-3*",
        "../ns-3*",
    ]
    
    # WSL-specific paths to check
    WSL_PATHS = [
        "~/ns-3-dev",
        "~/ns-allinone-3.*/ns-3.*",
        "~/ns3",
        "/opt/ns-3*",
        "/home/*/ns-3*",
    ]
    
    @classmethod
    def find_ns3_path(cls, check_wsl: bool = True) -> Optional[str]:
        """
        Search for ns-3 installation.
        
        Args:
            check_wsl: On Windows, also check inside WSL
            
        Returns:
            Path to ns-3 directory, or None if not found.
            On Windows with WSL, returns WSL path (e.g., ~/ns-3-dev)
        """
        import glob
        
        # First check native paths
        for pattern in cls.COMMON_PATHS:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded)
            for match in sorted(matches, reverse=True):
                if cls.validate_ns3_path(match):
                    return match
        
        # Try to find ns3 in PATH
        ns3_cmd = shutil.which("ns3")
        if ns3_cmd:
            ns3_dir = os.path.dirname(ns3_cmd)
            if cls.validate_ns3_path(ns3_dir):
                return ns3_dir
        
        # On Windows, check WSL
        if is_windows() and check_wsl and is_wsl_available():
            wsl_path = cls._find_ns3_in_wsl()
            if wsl_path:
                return wsl_path
        
        return None
    
    @classmethod
    def _find_ns3_in_wsl(cls) -> Optional[str]:
        """Search for ns-3 inside WSL."""
        for pattern in cls.WSL_PATHS:
            try:
                # Use WSL to expand glob and check
                cmd = f'for p in {pattern}; do [ -f "$p/ns3" ] && echo "$p" && break; done'
                result = subprocess.run(
                    ["wsl", "-e", "bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    # Validate it
                    if cls.validate_ns3_path_wsl(path):
                        return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        return None
    
    @classmethod
    def validate_ns3_path(cls, path: str, use_wsl: bool = False) -> bool:
        """
        Validate that a path contains a valid ns-3 installation.
        
        Args:
            path: Path to check (native or WSL path)
            use_wsl: If True, validate via WSL commands
            
        Returns:
            True if valid ns-3 installation
        """
        if use_wsl or (is_windows() and path.startswith(('/', '~'))):
            return cls.validate_ns3_path_wsl(path)
        
        if not os.path.isdir(path):
            return False
        
        # Check for ns3 script (ns-3.36+)
        ns3_script = os.path.join(path, "ns3")
        if os.path.isfile(ns3_script):
            return True
        
        # Check for waf script (older ns-3)
        waf_script = os.path.join(path, "waf")
        if os.path.isfile(waf_script):
            return True
        
        return False
    
    @classmethod
    def validate_ns3_path_wsl(cls, path: str) -> bool:
        """Validate ns-3 path inside WSL."""
        if not is_wsl_available():
            return False
        
        try:
            # Expand ~ and check for ns3 script
            cmd = f'[ -f "{path}/ns3" ] || [ -f "{path}/waf" ] && echo "valid"'
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == "valid"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @classmethod
    def get_ns3_version(cls, ns3_path: str, use_wsl: bool = False) -> Optional[str]:
        """
        Get ns-3 version string.
        
        Args:
            ns3_path: Path to ns-3 installation
            use_wsl: If True, read version via WSL
            
        Returns:
            Version string or None
        """
        if use_wsl or (is_windows() and ns3_path.startswith(('/', '~'))):
            return cls._get_ns3_version_wsl(ns3_path)
        
        version_file = os.path.join(ns3_path, "VERSION")
        if os.path.isfile(version_file):
            try:
                with open(version_file, "r") as f:
                    return f.read().strip()
            except Exception:
                pass
        
        # Try to extract from directory name
        dirname = os.path.basename(ns3_path)
        if "ns-3" in dirname or "ns3" in dirname:
            parts = dirname.replace("ns-3", "").replace("ns3", "").strip("-._")
            if parts:
                return parts
        
        return None
    
    @classmethod
    def _get_ns3_version_wsl(cls, ns3_path: str) -> Optional[str]:
        """Get ns-3 version from WSL."""
        try:
            cmd = f'cat "{ns3_path}/VERSION" 2>/dev/null || basename "{ns3_path}"'
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                # Clean up if it's just the directory name
                version = version.replace("ns-3", "").replace("ns3", "").strip("-._")
                return version if version else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None
    
    @classmethod
    def check_python_bindings(cls, ns3_path: str, use_wsl: bool = False) -> bool:
        """
        Check if ns-3 has Python bindings enabled.
        
        Args:
            ns3_path: Path to ns-3 installation
            use_wsl: Check via WSL
            
        Returns:
            True if Python bindings are available
        """
        if use_wsl or (is_windows() and ns3_path.startswith(('/', '~'))):
            return cls._check_python_bindings_wsl(ns3_path)
        
        # Check for build/bindings directory
        bindings_path = os.path.join(ns3_path, "build", "bindings", "python")
        if os.path.isdir(bindings_path):
            return True
        
        # Alternative location
        bindings_path = os.path.join(ns3_path, "build", "lib", "python")
        if os.path.isdir(bindings_path):
            return True
        
        return False
    
    @classmethod
    def _check_python_bindings_wsl(cls, ns3_path: str) -> bool:
        """Check Python bindings via WSL."""
        try:
            cmd = f'[ -d "{ns3_path}/build/bindings/python" ] || [ -d "{ns3_path}/build/lib/python" ] && echo "yes"'
            result = subprocess.run(
                ["wsl", "-e", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == "yes"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @classmethod
    def is_wsl_path(cls, path: str) -> bool:
        """Check if a path is a WSL path (Linux-style on Windows)."""
        if not is_windows():
            return False
        return path.startswith('/') or path.startswith('~')


class SimulationRunner(QObject):
    """
    Runs ns-3 simulation as subprocess.
    
    Uses QProcess for non-blocking execution with signal-based output.
    Supports both native execution and WSL on Windows.
    """
    
    # Signals
    started = pyqtSignal()
    finished = pyqtSignal(int, str)  # exit_code, output
    error = pyqtSignal(str)
    output_line = pyqtSignal(str)
    progress = pyqtSignal(int)  # percentage (0-100)
    
    def __init__(self, ns3_path: str = "", parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ns3_path = ns3_path
        self._process: Optional[QProcess] = None
        self._output_buffer: List[str] = []
        self._script_path: Optional[str] = None
        self._output_dir: Optional[str] = None
        self._use_wsl = False
        
    @property
    def ns3_path(self) -> str:
        return self._ns3_path
    
    @ns3_path.setter
    def ns3_path(self, value: str):
        self._ns3_path = value
        # Auto-detect if this is a WSL path
        self._use_wsl = NS3Detector.is_wsl_path(value)
    
    @property
    def use_wsl(self) -> bool:
        return self._use_wsl
    
    @use_wsl.setter
    def use_wsl(self, value: bool):
        self._use_wsl = value
    
    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running
    
    def run_script(self, script_content: str, output_dir: str) -> bool:
        """
        Run an ns-3 Python script.
        
        Args:
            script_content: The Python script content
            output_dir: Directory for output files (Windows path)
            
        Returns:
            True if started successfully
        """
        if self.is_running:
            self.error.emit("Simulation already running")
            return False
        
        # Validate ns-3 path
        if not self._ns3_path:
            self.error.emit("ns-3 path not configured")
            return False
        
        if not NS3Detector.validate_ns3_path(self._ns3_path, use_wsl=self._use_wsl):
            self.error.emit(f"Invalid ns-3 path: {self._ns3_path}")
            return False
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        self._output_dir = output_dir
        
        # Clear output buffer
        self._output_buffer = []
        
        if self._use_wsl:
            return self._run_script_wsl(script_content, output_dir)
        else:
            return self._run_script_native(script_content, output_dir)
    
    def _run_script_native(self, script_content: str, output_dir: str) -> bool:
        """Run script natively (Linux/macOS)."""
        # Save script to scratch directory
        scratch_dir = os.path.join(self._ns3_path, "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        
        self._script_path = os.path.join(scratch_dir, "gui_simulation.py")
        try:
            with open(self._script_path, "w") as f:
                f.write(script_content)
        except Exception as e:
            self.error.emit(f"Failed to write script: {e}")
            return False
        
        # Create process
        self._process = QProcess(self)
        self._process.setWorkingDirectory(self._ns3_path)
        
        # Connect signals
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        
        # Determine command
        ns3_script = os.path.join(self._ns3_path, "ns3")
        if os.path.isfile(ns3_script):
            program = ns3_script
            args = ["run", "scratch/gui_simulation.py"]
        else:
            program = os.path.join(self._ns3_path, "waf")
            args = ["--run", "scratch/gui_simulation"]
        
        # Set environment
        env = QProcess.systemEnvironment()
        lib_path = os.path.join(self._ns3_path, "build", "lib")
        env.append(f"LD_LIBRARY_PATH={lib_path}:$LD_LIBRARY_PATH")
        env.append(f"PYTHONPATH={self._ns3_path}/build/bindings/python:$PYTHONPATH")
        self._process.setEnvironment(env)
        
        # Start process
        self._process.start(program, args)
        
        if self._process.waitForStarted(5000):
            self.started.emit()
            return True
        else:
            self.error.emit("Failed to start ns-3 process")
            return False
    
    def _run_script_wsl(self, script_content: str, output_dir: str) -> bool:
        """Run script via WSL on Windows."""
        # Convert output dir to WSL path
        wsl_output_dir = windows_to_wsl_path(output_dir)
        
        # Update script to use WSL output path
        script_content = script_content.replace(output_dir, wsl_output_dir)
        script_content = script_content.replace(output_dir.replace('\\', '/'), wsl_output_dir)
        
        # Save script to Windows temp location first
        script_path = os.path.join(output_dir, "gui_simulation.py")
        try:
            with open(script_path, "w", newline='\n') as f:  # Use Unix line endings
                f.write(script_content)
        except Exception as e:
            self.error.emit(f"Failed to write script: {e}")
            return False
        
        self._script_path = script_path
        
        # Build WSL command
        wsl_script_path = windows_to_wsl_path(script_path)
        ns3_path = self._ns3_path
        
        # Expand ~ in ns3_path for the command
        if ns3_path.startswith('~'):
            ns3_path_expanded = ns3_path  # WSL will expand it
        else:
            ns3_path_expanded = ns3_path
        
        # Create the bash command to run
        # For ns-3.45+, we need to run Python scripts properly
        # Option 1: Use ns3 run with scratch-simulator style name
        # Option 2: Run Python directly with proper PYTHONPATH
        bash_cmd = f'''
set -e
cd {ns3_path_expanded}
echo "NS-3 Directory: $(pwd)"
echo "Copying script..."
cp "{wsl_script_path}" scratch/gui_simulation.py

# Try running with ns3 run first
echo "Attempting to run simulation..."
if ./ns3 run scratch/gui_simulation.py 2>&1; then
    echo "Simulation completed successfully"
else
    echo "ns3 run failed, trying alternative method..."
    # Alternative: run Python directly with proper paths
    export PYTHONPATH="$(pwd)/build/bindings/python:$PYTHONPATH"
    export LD_LIBRARY_PATH="$(pwd)/build/lib:$LD_LIBRARY_PATH"
    python3 scratch/gui_simulation.py 2>&1
fi
'''
        
        # Create process
        self._process = QProcess(self)
        
        # Connect signals
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished_wsl)
        self._process.errorOccurred.connect(self._on_error)
        
        # Start WSL process
        self._process.start("wsl", ["-e", "bash", "-c", bash_cmd])
        
        if self._process.waitForStarted(10000):
            self.started.emit()
            return True
        else:
            self.error.emit("Failed to start WSL process")
            return False
    
    def stop(self):
        """Stop the running simulation."""
        if self._process and self.is_running:
            self._process.terminate()
            if not self._process.waitForFinished(3000):
                self._process.kill()
    
    def _on_stdout(self):
        """Handle stdout from process."""
        if self._process:
            data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            for line in data.splitlines():
                self._output_buffer.append(line)
                self.output_line.emit(line)
                self._parse_progress(line)
    
    def _on_stderr(self):
        """Handle stderr from process."""
        if self._process:
            data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
            for line in data.splitlines():
                self._output_buffer.append(f"[stderr] {line}")
                self.output_line.emit(f"[stderr] {line}")
    
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion (native)."""
        output = "\n".join(self._output_buffer)
        self.finished.emit(exit_code, output)
        self._process = None
    
    def _on_finished_wsl(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion (WSL)."""
        # Copy results from WSL output location if needed
        # The script should have written to the shared folder already
        output = "\n".join(self._output_buffer)
        self.finished.emit(exit_code, output)
        self._process = None
    
    def _on_error(self, error: QProcess.ProcessError):
        """Handle process error."""
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start process",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error",
        }
        msg = error_messages.get(error, f"Process error: {error}")
        if self._use_wsl:
            msg += "\n\nMake sure WSL is installed and running."
        self.error.emit(msg)
    
    def _parse_progress(self, line: str):
        """Try to parse progress from output line."""
        import re
        
        # Pattern: time progress
        match = re.search(r"time[:\s]+(\d+\.?\d*)\s*/\s*(\d+\.?\d*)", line, re.IGNORECASE)
        if match:
            current = float(match.group(1))
            total = float(match.group(2))
            if total > 0:
                self.progress.emit(int(current / total * 100))
                return
        
        # Pattern: percentage
        match = re.search(r"(\d+)%", line)
        if match:
            self.progress.emit(int(match.group(1)))


class NS3SimulationManager(QObject):
    """
    High-level manager for ns-3 simulations.
    
    Coordinates script generation, running, and result parsing.
    Supports both native and WSL execution.
    """
    
    # Signals
    simulationStarted = pyqtSignal()
    simulationFinished = pyqtSignal(object)  # SimulationResults
    simulationError = pyqtSignal(str)
    outputReceived = pyqtSignal(str)
    progressUpdated = pyqtSignal(int)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ns3_path = ""
        self._use_wsl = False
        self._runner: Optional[SimulationRunner] = None
        self._output_dir = ""
        
        # Try to auto-detect ns-3
        detected = NS3Detector.find_ns3_path()
        if detected:
            self._ns3_path = detected
            self._use_wsl = NS3Detector.is_wsl_path(detected)
    
    @property
    def ns3_path(self) -> str:
        return self._ns3_path
    
    @ns3_path.setter
    def ns3_path(self, value: str):
        self._ns3_path = value
        self._use_wsl = NS3Detector.is_wsl_path(value)
    
    @property
    def use_wsl(self) -> bool:
        return self._use_wsl
    
    @use_wsl.setter
    def use_wsl(self, value: bool):
        self._use_wsl = value
    
    @property
    def ns3_available(self) -> bool:
        return bool(self._ns3_path) and NS3Detector.validate_ns3_path(
            self._ns3_path, use_wsl=self._use_wsl
        )
    
    @property
    def ns3_version(self) -> Optional[str]:
        if self._ns3_path:
            return NS3Detector.get_ns3_version(self._ns3_path, use_wsl=self._use_wsl)
        return None
    
    @property
    def is_running(self) -> bool:
        return self._runner is not None and self._runner.is_running
    
    @property
    def execution_mode(self) -> str:
        """Get description of execution mode."""
        if self._use_wsl:
            return "WSL"
        elif is_windows():
            return "Native Windows"
        else:
            return "Native"
    
    def run_simulation(
        self, 
        script_content: str, 
        output_dir: str
    ) -> bool:
        """
        Run a simulation with generated script.
        
        Args:
            script_content: Generated ns-3 Python script
            output_dir: Directory for output files (always Windows path on Windows)
            
        Returns:
            True if started successfully
        """
        if not self.ns3_available:
            msg = "ns-3 not found."
            if is_windows():
                msg += "\n\nOn Windows, you need:\n1. WSL installed (wsl --install)\n2. ns-3 installed inside WSL"
            msg += "\n\nPlease configure the path in settings."
            self.simulationError.emit(msg)
            return False
        
        self._output_dir = output_dir
        
        # Create runner
        self._runner = SimulationRunner(self._ns3_path, self)
        self._runner.use_wsl = self._use_wsl
        self._runner.started.connect(self._on_started)
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self._on_error)
        self._runner.output_line.connect(self.outputReceived)
        self._runner.progress.connect(self.progressUpdated)
        
        return self._runner.run_script(script_content, output_dir)
    
    def stop_simulation(self):
        """Stop the running simulation."""
        if self._runner:
            self._runner.stop()
    
    def _on_started(self):
        """Handle simulation start."""
        self.simulationStarted.emit()
    
    def _on_finished(self, exit_code: int, output: str):
        """Handle simulation completion."""
        from services.results_parser import ResultsParser
        from models import SimulationResults
        
        results = SimulationResults()
        results.console_output = output
        
        if exit_code == 0:
            results.success = True
            
            # Parse FlowMonitor results if available
            flowmon_path = os.path.join(self._output_dir, "flowmon-results.xml")
            if os.path.isfile(flowmon_path):
                parser = ResultsParser()
                results.flow_stats = parser.parse_flow_monitor_xml(flowmon_path)
            
            # Collect PCAP files
            import glob
            results.pcap_files = glob.glob(os.path.join(self._output_dir, "*.pcap"))
            
            # Set trace file path
            trace_path = os.path.join(self._output_dir, "trace.tr")
            if os.path.isfile(trace_path):
                results.trace_file_path = trace_path
        else:
            results.success = False
            results.error_message = f"Simulation failed with exit code {exit_code}"
            
            # Try to extract error from output
            if "error" in output.lower() or "exception" in output.lower():
                for line in output.split('\n'):
                    if 'error' in line.lower() or 'exception' in line.lower():
                        results.error_message += f"\n{line}"
                        break
        
        self.simulationFinished.emit(results)
    
    def _on_error(self, error_msg: str):
        """Handle simulation error."""
        self.simulationError.emit(error_msg)
