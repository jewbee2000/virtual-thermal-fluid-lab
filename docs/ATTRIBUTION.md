# Source and asset rights

Walter confirmed on 2026-10-06 that he authored the starter and selected MIT.
Root LICENSE covers project source. Codex assisted with implementation and review;
generated simulation evidence is not measured data. Scientific dependencies retain
their own package licenses. References are citations, not imported source text.

The code-native diagrams, CAD and simulation figures are project work. No stock
photographs or generated raster artwork are bundled. Hardware drawings are planned
designs, not photographs of fabricated equipment.

The offline replay bundles uPlot1.6.32 under MIT, including its original notice in
`web/vendor/uplot/LICENSE`. The exporter copies Walter's root MIT notice to
`LICENSE.txt` and includes it in the replay artifact hashes. The chart JS/CSS
files are pinned in `web/THIRD_PARTY.md`.

Pico SDK2.3.1 and pinned TinyUSB86ad6e56c1700e85f1c5678607a762cfe3aa2f47
are external build inputs. The firmware distribution retains SDK BSD-3-Clause
and linked TinyUSB MIT notices in `firmware/pico/THIRD_PARTY_LICENSES.txt`,
including Raspberry Pi, Ha Thach2018/2019/2021 and Reinhard Panhuber2020 source
attributions. Linked Pico printf retains Marco Paland2014–2019 MIT attribution;
the original SDK printf LICENSE is also in `third_party/licenses`.

The actual link maps allocate newlib `libg.a` members `libc_a-memmove.o` and
`libc_a-strlen-stub.o`, and libgcc `_dvmd_tls.o`. LOAD listings for `libstdc++`,
`libm` and `libc` do not establish allocated code from those archives. The ARM
toolchain header identifies newlib4.5.0. `third_party/licenses/COPYING.NEWLIB-4.5.0`
retains the broad upstream notice inventory from the official
newlib4.5.0.20241231 source archive. That does not establish exact identity of
Arm's patched runtime; its exact patched-source mapping remains unresolved.

`third_party/licenses/GPL-3.0.txt` and `GCC-exception-3.1.txt` are original GCC15.2.0
release notices. The primary libgcc ARM source identifies `_dvmd_tls` under GPL3
or later with Runtime Library Exception3.1. This project uses an ordinary GCC
target compilation; its core source is MIT. The package retains both notices and
does not redistribute the toolchain itself. This is a bounded notice/source audit,
not a claim that upstream releases exactly reproduce every Arm patch.

Planned build-tool dependencies stay external/ignored: CMake4.4.4 BSD-3-Clause
(LICENSE.rst/Licenses), Ninja1.13.2 Apache-2.0 (COPYING), Pico SDK2.3.1 BSD-3-Clause
(LICENSE.TXT), ARM GCC15.2.rel1 GNU notices (share/doc/gcc/Copying.html and
share/doc/gdb/Copying.html). Retain original packages/notices; target runtime
redistribution notices accompany the actual linked firmware. Toolchain, SDK,
Python environments, installers and account data remain excluded from curated
release ZIPs. Final ZIP contents are checked before publishing. Scientific wheels
are installed from the preserved lock rather than redistributed.

Primary sources: [Pico SDK](https://github.com/raspberrypi/pico-sdk/tree/079c6f39023649b154152db30f1d781e884879bc),
[TinyUSB](https://github.com/hathach/tinyusb/tree/86ad6e56c1700e85f1c5678607a762cfe3aa2f47),
[uPlot1.6.32](https://github.com/leeoniya/uPlot/tree/1.6.32),
[newlib source](https://sourceware.org/pub/newlib/),
[GCC runtime exception](https://www.gnu.org/licenses/gcc-exception-3.1.html),
[GCC15.2.0 ARM runtime source](https://github.com/gcc-mirror/gcc/blob/releases/gcc-15.2.0/libgcc/config/arm/lib1funcs.S).
