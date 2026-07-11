import sys
import os

# Allow importing root-level modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from automation_wrapper import DeviceAutomationManager
