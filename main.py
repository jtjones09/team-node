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
    """Show usage dashboard in terminal."""
    from tracking.usage_tracker import UsageTracker

    tracker = UsageTracker()

    if args.usage_export:
        print(tracker.export_json(
            project=args.project,
            limit=args.usage_limit or 100,
        ))
        return

    group_by = args.usage_group or "model"
    summary = tracker.summary(project=args.project, group_by=group_by)

    if not summary:
        print("No usage data yet. Run some agents first!")
        return

    print(f"\n  Usage Summary (grouped by {group_by})")
    print("  " + "=" * 60)
    total_cost = 0.0
    total_calls = 0
    for row in summary:
        group_val = row.get(group_by, "unknown")
        calls = row.get("call_count", 0)
        tokens = row.get("total_tokens", 0)
        cost = row.get("total_cost_usd", 0.0)
        total_cost += cost
        total_calls += calls
        print(f"  {group_val:<30} {calls:>5} calls  {tokens:>10,} tokens  ${cost:>8.4f}")
    print("  " + "-" * 60)
    print(f"  {'TOTAL':<30} {total_calls:>5} calls  {'':>10}  ${total_cost:>8.4f}")

    if args.project:
        print(f"\n  (filtered to project: {args.project})")

    # Show available tags
    tags = tracker.get_all_tags()
    if tags:
        print(f"\n  Tags: {', '.join(tags)}")

    projects = tracker.get_all_projects()
    if projects:
        print(f"  Projects: {', '.join(projects)}")
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

    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    if args.usage or args.usage_export:
        run_usage(args)
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
    from tracking.usage_tracker import UsageTracker
    from tracking.crew_callbacks import log_crew_run

    tracker = UsageTracker()
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

    # Auto-save HTML mockups
    saved_path = _extract_and_save_html(str(result), args.project)
    if saved_path:
        print(f"  HTML mockup saved to: {saved_path}")
        print(f"  Open in browser: file://{Path(saved_path).resolve()}")


if __name__ == "__main__":
    main()
