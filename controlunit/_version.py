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


# The major number names an era of the program, by owner decision
# 2026-09-04: 0 the prototypes, 1 the later updates, 2 the half-transition
# to separate workers, 3 the thread fix the rig actually ran, 4 the rig on
# the lab network. The second number moves for a feature, the third for a
# fix; pyproject.toml carries the same number and a test holds them equal.
# docs/history.md tells the eras in full.
__version__ = "4.2.0"

__about__ = """
Version 4: the rig on the lab network.

Three devices are read and driven: the I2C ADC for signal records, the
DAC8532 board for the mass-flow controllers, and the MCP4725 DAC for the
plasma current. Beside the Qt window an optional web view, started with
--web and on by default from the rig's launcher, serves a health report for
the lab's ensemble of three services and four tabs: Live, the rig's values
and three strip charts (plasma current, the ion gauges, the Baratrons) with
big readouts, a fast poll, a median smoothing and a day of history kept in
the browser; Control, which lets a browser start and stop acquisition, set
the sampling time, gas flow, plasma current, gauge mode and range, the QMS
sync line and the Ip/Bu/Bd baselines behind a Remote switch on the rig's
own screen, with Stop all outputs always allowed, acting under a name from
the lab's roster and behind the lab's word; Log, the message log; and Lab,
the three services and how each is started, drawn at once and asked in the
background. Every browser command is queued and run by the Qt main thread
through the same methods the rig's own buttons call.
"""
