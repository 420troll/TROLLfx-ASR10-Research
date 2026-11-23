# Third-party notices

## MAME ES5510 processor

`mame_es5510_standalone.cpp` is an isolated adapter/port of the execution,
register, ALU, MAC and memory-pipeline behavior in MAME's ES5510 device. It was
written against MAME commit
[`8be57cdc5f44ab830dff44c06dd39f24190742d4`](https://github.com/mamedev/mame/tree/8be57cdc5f44ab830dff44c06dd39f24190742d4/src/devices/cpu/es5510),
principally `src/devices/cpu/es5510/es5510.cpp` and `es5510.h`. Audio serial
bus routing follows `src/devices/sound/esqpump.cpp`. No MAME framework source,
ROM, firmware, factory microprogram, or third-party emulator code is linked.

Copyright Christian Brunschen and MAMEdev contributors.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

This is an independent research adapter and is not affiliated with or endorsed
by MAMEdev. Ensoniq firmware and effect programs are not included or licensed
by this notice.
