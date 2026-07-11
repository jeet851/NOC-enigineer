# ai_engine package
from ai_engine.engine import AIEngineWrapper
import importlib.util
import os
import sys

# Dynamically load the root-level ai_engine.py module to resolve naming collision
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../ai_engine.py"))
if os.path.exists(root_path):
    try:
        spec = importlib.util.spec_from_file_location("ai_engine_root", root_path)
        ai_engine_root = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ai_engine_root)
        
        # Merge all attributes from the root module into the package namespace
        for attr in dir(ai_engine_root):
            if not attr.startswith("__"):
                globals()[attr] = getattr(ai_engine_root, attr)
    except Exception as e:
        print(f"Warning: could not import root ai_engine module dynamically: {e}")
else:
    print("Warning: root-level ai_engine.py not found.")
