"""CLI entry point for TeamNode."""

import argparse
import re
import sys
import time
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
    """If the result contains HTML, save it to data/outputs/."""
    text = str(result_text)
    html_match = re.search(r'(<!DOCTYPE html>.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if not html_match:
        html_match = re.search(r'(<html.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if not html_match:
        return None
    html_content = html_match.group(1)
    if len(html_content) < 200:
        return None
    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{project}-mockup.html" if project else "mockup.html"
    output_path = output_dir / filename
    output_path.write_text(html_content)
    return str(output_path)


def run_usage(args):
    """Show usage dashboard from fabric."""
    from tracking.fabric_tracker import FabricTracker

    tracker = FabricTracker(project=args.project or "default")

    if args.usage_export:
        print(tracker.export_json(
            project=args.project,
            limit=args.usage_limit or 100,
        ))
        return

    group_by = args.usage_group or "model"
    summary_json = tracker.summary(project=args.project, group_by=group_by)

    print(f"\n  Usage Summary (grouped by {group_by})")
    print("  " + "=" * 60)
    print(f"  {summary_json}")

    total = tracker.total_cost(project=args.project)
    print(f"\n  Total cost: ${total:.4f}")

    if args.project:
        print(f"  (filtered to project: {args.project})")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="TeamNode: 7-agent heterogeneous fabric team",
    )
    parser.add_argument("--goal", type=str, help="The goal or task for the team.")
    parser.add_argument("--project", type=str, default=None, help="Project name for scoped memory.")
    parser.add_argument("--list-projects", action="store_true", help="List all available projects.")
    parser.add_argument("--history", action="store_true", help="Show provenance history (requires --project).")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose agent output.")
    parser.add_argument("--setup", action="store_true", help="Configure API key.")
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local inference.")
    parser.add_argument("--model", type=str, default=None, help="Override Ollama model.")

    # Usage tracking
    parser.add_argument("--usage", action="store_true", help="Show usage summary.")
    parser.add_argument("--usage-group", type=str, default=None,
                        help="Group usage by: model, domain, project, tier, operation")
    parser.add_argument("--usage-export", action="store_true", help="Export usage as JSON.")
    parser.add_argument("--usage-limit", type=int, default=None, help="Limit export rows.")

    # Model tier override
    parser.add_argument("--fast", action="store_true", help="Force all agents to use Haiku (cheapest).")
    parser.add_argument("--premium", action="store_true", help="Force all agents to use Opus (best quality).")

    # Heartbeat
    parser.add_argument("--heartbeat", action="store_true", help="Run heartbeat pulse (once or daemon).")
    parser.add_argument("--daemon", action="store_true", help="Run heartbeat as a repeating daemon.")

    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    if args.usage or args.usage_export:
        run_usage(args)
        return

    if args.heartbeat:
        from heartbeat.pulse import Heartbeat
        hb = Heartbeat(project=args.project or "default")
        if args.daemon:
            hb.run_daemon()
        else:
            hb.pulse()
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
        from tracking.continuity import ContinuityThread
        continuity = ContinuityThread(project=args.project)
        # Search for all session summaries
        import subprocess
        from config import FABRIC_BINARY
        result = subprocess.run(
            [FABRIC_BINARY, "fabric", "search",
             "--where", f"kind=session_summary AND project={args.project}",
             "--limit", "20",
             "--project", args.project],
            capture_output=True, text=True, timeout=30,
        )
        if not result.stdout.strip() or "No matching" in result.stdout:
            print(f"No session history for project '{args.project}'.")
        else:
            print(f"Session history for '{args.project}':")
            print("-" * 60)
            print(result.stdout)
        return

    if not args.goal:
        parser.error("--goal is required (unless using --setup, --list-projects, --history, or --usage)")

    if not args.ollama:
        api_key = get_api_key()
        if not api_key:
            print("Error: No Anthropic API key found.")
            print("Set ANTHROPIC_API_KEY or run: python main.py --setup")
            sys.exit(1)

    # Determine force tier
    from routing.model_router import ModelTier
    force_tier = None
    if args.fast:
        force_tier = ModelTier.FAST
    elif args.premium:
        force_tier = ModelTier.PREMIUM

    from crew import build_crew

    crew = build_crew(
        goal=args.goal,
        verbose=not args.quiet,
        use_ollama=args.ollama,
        ollama_model=args.model,
        project=args.project,
        force_tier=force_tier,
    )

    # Track the run
    from tracking.fabric_tracker import FabricTracker
    from tracking.crew_callbacks import log_crew_run

    tracker = FabricTracker(project=args.project or "default")
    start_time = time.time()

    result = crew.kickoff()

    elapsed_ms = int((time.time() - start_time) * 1000)

    print("\n" + "=" * 60)
    print("TEAM RESULT")
    print("=" * 60)
    print(result)

    # Log the run
    meta = getattr(crew, "_teamnode_meta", {})
    event_id = log_crew_run(
        tracker=tracker,
        project=meta.get("project", args.project or ""),
        goal=args.goal,
        domains=meta.get("domains", []),
        models=meta.get("models", {}),
        tiers=meta.get("tiers", {}),
        result=result,
        duration_ms=elapsed_ms,
    )
    print(f"\n  Run tracked: {event_id} ({elapsed_ms/1000:.1f}s)")
    print(f"  Usage: python main.py --usage --project {args.project or 'all'}")

    # Store session summary for continuity
    if args.project:
        try:
            from tracking.continuity import ContinuityThread
            continuity = ContinuityThread(project=args.project)
            result_summary = str(result)[:200] if result else "completed"
            continuity.store_session_summary(
                description=f"{args.goal[:100]}. Result: {result_summary}",
                agents=meta.get("domains", []),
                models=list(meta.get("models", {}).values()),
                cost=0.0,  # Will be enriched by fabric tracker
                duration_ms=elapsed_ms,
            )
            print(f"  Session summary stored for continuity.")
        except Exception as e:
            print(f"  Warning: could not store session summary: {e}")

    # Auto-save HTML mockups
    saved_path = _extract_and_save_html(str(result), args.project)
    if saved_path:
        print(f"  HTML mockup saved to: {saved_path}")
        print(f"  Open in browser: file://{Path(saved_path).resolve()}")


if __name__ == "__main__":
    main()
