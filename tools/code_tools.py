"""Code execution and analysis tools."""

import subprocess
import tempfile
from pathlib import Path

from crewai.tools import tool


@tool("Run Python Code")
def run_python_code(code: str) -> str:
    """Execute a Python code snippet in a sandboxed subprocess.

    Args:
        code: Python code to execute.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                ["python", f.name],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: code execution timed out (30s limit)."
        finally:
            Path(f.name).unlink(missing_ok=True)


@tool("Analyze Code File")
def analyze_code_file(file_path: str) -> str:
    """Read and return the contents of a code file for analysis.

    Args:
        file_path: Path to the file to analyze.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if path.stat().st_size > 100_000:
        return f"File too large ({path.stat().st_size} bytes). Read a smaller file or specific section."
    return path.read_text()
