#!/usr/bin/env python3
"""
Script to purge all "topics" lists in exams.json by setting each to an empty list.
"""
import json
import sys
from project_config import *


def purge_temaer():
    """
    Load the JSON, clear all Temaer, and save back the file.
    """
    try:
        with EXAMS_JSON.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Clear Temaer for each entry
    for entry in data:
        entry['Temaer'] = []

    try:
        with EXAMS_JSON.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Error writing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ All topics lists in '{EXAMS_JSON.name}' have been purged.")


if __name__ == '__main__':
    purge_temaer()
