"""
Plasma Control Unit
https://github.com/queezz/ControlUnit/tree/pack
https://queezz.github.io/ControlUnit/
"""
import pathlib
import sys

# temporarily add this module's directory to PATH
_echelle_base = pathlib.Path(__file__).parent.absolute()
sys.path.append(str(_echelle_base))

# remove unneeded names from namespace
del pathlib, sys
