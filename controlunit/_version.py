# Copyright 2022 Arseniy
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__version__ = "0.7.0"

__about__ = """
In this version we use two devices:
- I2C ADC for signal records
- DAC8532 AD/DA board for MFCs control
- MCP4725 DAC for plasma current control

This version adds an optional read-only web view, started with --web: a
health report, a Live tab with the rig's values and two strip charts, a Log
tab with the message log, and a Lab tab showing the three lab services.

This version adds browser control on a Control tab: gas flow, plasma
current, gauge mode and range, the QMS sync line, and the baselines of Ip,
Bu and Bd can be set from a laptop. Setting is gated by a Remote switch on
the rig's own screen and a name chosen in the browser; stopping every output
is always allowed. A browser's instruction is queued and run by the Qt main
thread, which calls the same methods the rig's own buttons call.
"""
