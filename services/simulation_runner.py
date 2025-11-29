"""
NS-3 Simulation Runner.

Manages ns-3 subprocess execution and output capture.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QTimer


class NS3Detector:
    """
    Auto-detect ns-3 installation.
    
    Searches common locations and validates the installation.
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
    
    @classmethod
    def find_ns3_path(cls) -> Optional[str]:
        """
        Search for ns-3 installation.
        
        Returns:
            Path to ns-3 directory, or None if not found.
        """
        import glob
        
        for pattern in cls.COMMON_PATHS:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded)
            for match in sorted(matches, reverse=True):  # Prefer newer versions
                if cls.validate_ns3_path(match):
                    return match
        
        # Try to find ns3 in PATH
        ns3_cmd = shutil.which("ns3")
        if ns3_cmd:
            # ns3 script is usually in the ns-3 root directory
            ns3_dir = os.path.dirname(ns3_cmd)
            if cls.validate_ns3_path(ns3_dir):
                return ns3_dir
        
        return None
    
    @classmethod
    def validate_ns3_path(cls, path: str) -> bool:
        """
        Validate that a path contains a valid ns-3 installation.
        
        Args:
            path: Path to check
            
        Returns:
            True if valid ns-3 installation
        """
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
    def get_ns3_version(cls, ns3_path: str) -> Optional[str]:
        """
        Get ns-3 version string.
        
        Args:
            ns3_path: Path to ns-3 installation
            
        Returns:
            Version string or None
        """
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
    def check_python_bindings(cls, ns3_path: str) -> bool:
        """
        Check if ns-3 has Python bindings enabled.
        
        Args:
            ns3_path: Path to ns-3 installation
            
        Returns:
            True if Python bindings are available
        """
        # Check for build/bindings directory
        bindings_path = os.path.join(ns3_path, "build", "bindings", "python")
        if os.path.isdir(bindings_path):
            return True
        
        # Alternative location
        bindings_path = os.path.join(ns3_path, "build", "lib", "python")
        if os.path.isdir(bindings_path):
            return True
        
        return False


class SimulationRunner(QObject):
    """
    Runs ns-3 simulation as subprocess.
    
    Uses QProcess for non-blocking execution with signal-based output.
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
        
    @property
    def ns3_path(self) -> str:
        return self._ns3_path
    
    @ns3_path.setter
    def ns3_path(self, value: str):
        self._ns3_path = value
    
    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running
    
    def run_script(self, script_content: str, output_dir: str) -> bool:
        """
        Run an ns-3 Python script.
        
        Args:
            script_content: The Python script content
            output_dir: Directory for output files
            
        Returns:
            True if started successfully
        """
        if self.is_running:
            self.error.emit("Simulation already running")
            return False
        
        if not self._ns3_path or not NS3Detector.validate_ns3_path(self._ns3_path):
            self.error.emit(f"Invalid ns-3 path: {self._ns3_path}")
            return False
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        self._output_dir = output_dir
        
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
        
        # Clear output buffer
        self._output_buffer = []
        
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
            # ns-3.36+ uses ns3 script
            program = ns3_script
            args = ["run", "scratch/gui_simulation.py"]
        else:
            # Older ns-3 uses waf
            program = os.path.join(self._ns3_path, "waf")
            args = ["--run", "scratch/gui_simulation"]
        
        # Set environment
        env = QProcess.systemEnvironment()
        # Add ns-3 library path
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
                
                # Try to parse progress from output
                self._parse_progress(line)
    
    def _on_stderr(self):
        """Handle stderr from process."""
        if self._process:
            data = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
            for line in data.splitlines():
                self._output_buffer.append(f"[stderr] {line}")
                self.output_line.emit(f"[stderr] {line}")
    
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion."""
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
        self.error.emit(error_messages.get(error, f"Process error: {error}"))
    
    def _parse_progress(self, line: str):
        """Try to parse progress from output line."""
        # Look for patterns like "Simulation time: 5.0s / 10.0s"
        # or percentage indicators
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
        self._runner: Optional[SimulationRunner] = None
        self._output_dir = ""
        
        # Try to auto-detect ns-3
        detected = NS3Detector.find_ns3_path()
        if detected:
            self._ns3_path = detected
    
    @property
    def ns3_path(self) -> str:
        return self._ns3_path
    
    @ns3_path.setter
    def ns3_path(self, value: str):
        self._ns3_path = value
    
    @property
    def ns3_available(self) -> bool:
        return bool(self._ns3_path) and NS3Detector.validate_ns3_path(self._ns3_path)
    
    @property
    def ns3_version(self) -> Optional[str]:
        if self._ns3_path:
            return NS3Detector.get_ns3_version(self._ns3_path)
        return None
    
    @property
    def is_running(self) -> bool:
        return self._runner is not None and self._runner.is_running
    
    def run_simulation(
        self, 
        script_content: str, 
        output_dir: str
    ) -> bool:
        """
        Run a simulation with generated script.
        
        Args:
            script_content: Generated ns-3 Python script
            output_dir: Directory for output files
            
        Returns:
            True if started successfully
        """
        if not self.ns3_available:
            self.simulationError.emit("ns-3 not found. Please configure the path in settings.")
            return False
        
        self._output_dir = output_dir
        
        # Create runner
        self._runner = SimulationRunner(self._ns3_path, self)
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
        
        self.simulationFinished.emit(results)
    
    def _on_error(self, error_msg: str):
        """Handle simulation error."""
        self.simulationError.emit(error_msg)
