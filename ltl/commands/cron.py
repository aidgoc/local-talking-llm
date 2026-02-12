"""Cron command - Manage scheduled tasks."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def list_tasks(args):
    """List all scheduled tasks."""
    print("📅 Scheduled Tasks\n")
    print("=" * 60)
    print("\nNo scheduled tasks yet.")
    print("\nTo add a task:")
    print("  ltl cron add -n 'reminder' -m 'Take a break' -e 3600")
    print("=" * 60)


def add_task(args):
    """Add a scheduled task."""
    print(f"📅 Adding Task: {args.name}")
    print(f"   Message: {args.message}")

    if args.every:
        print(f"   Schedule: Every {args.every} seconds")
    elif args.at:
        print(f"   Schedule: At timestamp {args.at}")

    print("\n✓ Task added (placeholder - full implementation coming soon)")


def remove_task(args):
    """Remove a scheduled task."""
    print(f"📅 Removing Task: {args.task_id}")
    print("\n✓ Task removed (placeholder - full implementation coming soon)")
