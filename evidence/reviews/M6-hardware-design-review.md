# Hardware packet design review

Read-only internal review by replay_writer on2026-10-06 at cc5a6fe. ACCEPT after
the peripheral-U repair. This reviewer helped author the packet; this is a
consistency check, not independent empirical or physical validation.

Inspected docs/hardware/PACKET.md, breadboard_plate.scad, both hardware SVGs,
MCU_CONTRACT.md and Pico HAL/device-policy source. Millimetre dimensions, slot
coordinates and CAD/SVG orientation agree. GP functions and voltage-emulation
mapping agree with firmware. Primary manufacturer documentation confirms GP25
LED, 3V3 pin36 and AGND pin33. Status labels are honest.

The review found peripheral mode accepted external U despite the frozen
GPIO-only ARM/RESET policy. The coordinator added the mode1 guard and a native
regression test. Actual before-fix CTest failed; after-fix213policy checks,
27HAL checks and1000 bounded USB passes succeeded. The reviewer inspected the
repair and test source but ran no tests/builds/simulations or file edits.

Remaining uncertainty: CAD render, breadboard fit, material/kerf tolerances,
cable access and retention have no physical evidence. Cable slots leave a2mm
edge ligament requiring the planned coupon/fit check. Fixture NOT_FABRICATED,
board NOT_EXECUTED, physical validation NOT_STARTED.
