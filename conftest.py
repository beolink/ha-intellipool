"""Root conftest: make the repo importable so `custom_components.*` resolves."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
