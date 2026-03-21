"""CLI entry point for TeamNode."""

import argparse
import sys

from config import ANTHROPIC_API_KEY


def main():
    parser = argparse.ArgumentParser(
        description="TeamNode: 7-agent heterogeneous fabric team",
    )
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="The goal or task for the team to accomplish.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose agent output.",
    )
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Export it before running: export ANTHROPIC_API_KEY='your-key'")
        sys.exit(1)

    from crew import build_crew

    crew = build_crew(goal=args.goal, verbose=not args.quiet)
    result = crew.kickoff()
    print("\n" + "=" * 60)
    print("TEAM RESULT")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
