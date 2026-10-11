import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "src"))

from ultra_ac.app import main

if __name__ == "__main__":
    raise SystemExit(main())
