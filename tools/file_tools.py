"""File system operation tools."""

from pathlib import Path

from crewai.tools import tool


@tool("Read File")
def read_file(file_path: str) -> str:
    """Read the contents of a file.

    Args:
        file_path: Path to the file to read.
    """
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if path.stat().st_size > 100_000:
        return f"File too large ({path.stat().st_size} bytes)."
    return path.read_text()


@tool("Write File")
def write_file(file_path: str, content: str) -> str:
    """Write content to a file, creating parent directories if needed.

    Args:
        file_path: Path to the file to write.
        content: Content to write to the file.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"Written {len(content)} bytes to {file_path}"


@tool("List Directory")
def list_directory(dir_path: str = ".") -> str:
    """List files and directories in a given path.

    Args:
        dir_path: Directory path to list.
    """
    path = Path(dir_path)
    if not path.exists():
        return f"Directory not found: {dir_path}"
    if not path.is_dir():
        return f"Not a directory: {dir_path}"
    entries = sorted(path.iterdir())
    lines = []
    for entry in entries[:100]:
        prefix = "d " if entry.is_dir() else "f "
        lines.append(f"{prefix}{entry.name}")
    if len(entries) > 100:
        lines.append(f"... and {len(entries) - 100} more entries")
    return "\n".join(lines) or "(empty directory)"
