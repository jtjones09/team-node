"""CLI entry point for TeamNode."""

import argparse
import re
import sys
from pathlib import Path

from config import get_api_key, save_api_key, list_projects


def run_setup():
    """Prompt for API key and save to persistent config."""
    print("TeamNode Setup")
    print("-" * 40)
    key = input("Enter your Anthropic API key: ").strip()
    if not key:
        print("No key entered. Aborting.")
        sys.exit(1)
    path = save_api_key(key)
    print(f"API key saved to {path} (permissions: 0600)")
    print("You can now run team-node without setting ANTHROPIC_API_KEY.")


def _extract_and_save_html(result_text: str, project: str | None) -> str | None:
    """If the result contains HTML, save it to data/outputs/.

    Returns the saved file path, or None if no HTML was found.
    """
    text = str(result_text)

    # Look for HTML content in the result
    html_match = re.search(r'(<!DOCTYPE html>.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if not html_match:
        html_match = re.search(r'(<html.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if not html_match:
        return None

    html_content = html_match.group(1)
    if len(html_content) < 200:
        return None  # Too short to be a real mockup

    # Save to data/outputs/
    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{project}-mockup.html" if project else "mockup.html"
    output_path = output_dir / filename
    output_path.write_text(html_content)
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="TeamNode: 7-agent heterogeneous fabric team",
    )
    parser.add_argument(
        "--goal",
        type=str,
        help="The goal or task for the team to accomplish.",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Project name for scoped memory and logs.",
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List all available projects.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show recent provenance history for a project (requires --project).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose agent output.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Configure API key and save to ~/.config/teamnode/config.json.",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Use Ollama for local inference instead of Anthropic.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the Ollama model (default: llama3.2:3b). Only used with --ollama.",
    )
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    if args.list_projects:
        projects = list_projects()
        if projects:
            print("Available projects:")
            for p in projects:
                print(f"  - {p}")
        else:
            print("No projects found. Create one with: --project <n> --goal <task>")
        return

    if args.history:
        if not args.project:
            parser.error("--history requires --project")
        from memory.provenance import ProvenanceTracker
        from config import get_project_paths
        paths = get_project_paths(args.project)
        tracker = ProvenanceTracker(str(paths["project_dir"]))
        entries = tracker.get_recent(limit=20)
        if not entries:
            print(f"No provenance history for project '{args.project}'.")
        else:
            print(f"Provenance history for '{args.project}' ({len(entries)} entries):")
            print("-" * 60)
            for entry in entries:
                ts = entry.get("timestamp", "unknown")
                agent = entry.get("agent", "unknown")
                etype = entry.get("type", "unknown")
                summary = entry.get("output_summary", entry.get("decision", ""))[:100]
                print(f"  [{ts}] {agent} ({etype}): {summary}")
        return

    if not args.goal:
        parser.error("--goal is required (unless using --setup, --list-projects, or --history)")

    if not args.ollama:
        api_key = get_api_key()
        if not api_key:
            print("Error: No Anthropic API key found.")
            print("Set ANTHROPIC_API_KEY or run: python main.py --setup")
            sys.exit(1)

    from crew import build_crew

    crew = build_crew(
        goal=args.goal,
        verbose=not args.quiet,
        use_ollama=args.ollama,
        ollama_model=args.model,
        project=args.project,
    )
    result = crew.kickoff()
    print("\n" + "=" * 60)
    print("TEAM RESULT")
    print("=" * 60)
    print(result)

    # Auto-save HTML mockups if the result contains HTML
    saved_path = _extract_and_save_html(str(result), args.project)
    if saved_path:
        print(f"\n  HTML mockup saved to: {saved_path}")
        print(f"  Open in browser: file://{Path(saved_path).resolve()}")


if __name__ == "__main__":
    main()
