import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mbq_wedge import MBQWedge

NODE_CLASS_MAPPINGS        = {"MBQWedge": MBQWedge}
NODE_DISPLAY_NAME_MAPPINGS = {"MBQWedge": "MBQ Wedge"}
WEB_DIRECTORY              = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
