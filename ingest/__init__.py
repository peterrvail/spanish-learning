"""Lesson-screenshot ingestion: data contracts now, the script in scripts/ingest.py later.

Not imported by the Streamlit app. Shares the concept taxonomy with it."""
import os
import sys

_APP = os.path.join(os.path.dirname(__file__), "..", "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)
