# Planned hardware and fabrication packet

Status: **NOT_FABRICATED** fixture, **NOT_EXECUTED** board demonstration,
**NOT_STARTED** physical validation. No real pump, heater or valve is connected
by this packet. Native target cross-build evidence is a separate milestone.

The [instrument concept](../../hardware/instrumented_loop.svg) locates future
thermal-loop measurements. The immediate H1 demonstration uses an RP2040 Pico
and a voltage knob to emulate the existing tank, exercising acquisition and
supervision without a water or heated rig. The knob mapping is assumed, not a
calibrated level measurement. A Pico W/Pico 2 is not the declared GP25-LED target;
confirm the actual board before flashing the RP2040 non-wireless build.

## I/O and acquisition

Frozen source: `docs/MCU_CONTRACT.md`. Verify board pin labels against the
[manufacturer documentation](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html)
and [Pico datasheet](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)
before wiring. Board pin numbers below are for non-wireless Pico/Pico H, using
the documented top-view numbering; GP numbers remain the firmware contract.

| Signal | GP / physical pin | Planned interface | Acquisition / evidence |
| --- | --- | --- | --- |
| Level emulation | GP26 / ADC0 / pin31 | 10 kΩ nominal potentiometer between 3V3(OUT) pin36 and AGND pin33; wiper to GP26. Nominal 0–3.3 V → 0–1 m assumed map | Default 100 ms configured tick; local D acquisition; ADC deadline100 µs plus bounded iteration guard; timeout is invalid. Actual voltage/reference/noise not measured |
| Separate trip | GP14 / pin19 | Active HIGH with internal pull-up; removable jumper to GND pin18 clears; disconnect asserts | GPIO sampled at local D tick; acquire trip separately from ADC |
| ARM | GP15 / pin20 | Momentary connection to GND; active LOW pull-up, new sampled press edge | Held-at-boot must not arm; explicit guarded operation |
| RESET | GP16 / pin21 | Momentary connection to GND pin23; active LOW pull-up, new sampled press edge | Clears latched trip only with valid clear inputs, returns DISARMED; separate ARM needed |
| Status indicator | GP25 / onboard LED | Indicator only on non-wireless Pico | No heater/pump/valve electrical output |
| Transport | USB micro-B | Host USB power/data; synthetic-link and peripheral firmware builds are distinct | Save B/X/N/Q/R plus configuration and host timestamps, rejected/drop counters and reset cause |

Only the Pico's own 3V3 reference and ground feed this emulation. Measure the
wiper voltage with a DMM before connecting GP26; do not apply a 5 V signal.
The 0–3.3 V value is the design's nominal range, not a measured calibration or
an inferred absolute-maximum rating. Record the actual board marking and USB
cable identity; unplug USB while installing or changing jumpers.

Peripheral mode obtains tank channels1/6 from ADC/GPIO and rejects external O/U
replacement. Synthetic-link mode accepts externally declared observations and
intent; their source clock is not synchronized to the device. X diagnostics
state acquisition kind and retain source/receipt clocks. Do not subtract a
source V timestamp from local D time. Default tick100 ms and watchdog1500 ms
are configured design values; executed intervals/overruns/reset timing require
the H1 capture below. The firmware supported1–1000 ms tick range is not a
measured timing guarantee.

## Future instrument concept

| Virtual instrument | Intended quantity / nominal envelope | Pedigree and next measurement |
| --- | --- | --- |
| TT-01/TT-02/TT-03 | Hot liquid, cooled liquid, wall; model273.15–368.15 K domain | Model domain assumed, not selected sensor range. Select sensing/attachment only after actual rig exists; compare independent reference and report lag/uncertainty |
| FT-01 | Volume flow target0.00015 m³/s (9 L/min); controller0–0.0005 m³/s range | Assumed controller envelope; distinguish mass flow from volume flow. Ambient tank collection over known time supplies an independent baseline |
| PT-01 | Pump differential; nominal18.825 kPa at9 L/min in assumed model | Two pressure references needed for differential; no pressure transducer selected or installed |
| TSHH | Separate wall-trip logic at358.15 K (85 °C) in SIL | Ideal independent switch assumed. GP14 demonstrates logic only, not thermal trip accuracy or independence of physical sensors |
| Heat input / sink | Virtual5000 W heat, UAc500 W/K nominal | Assumed model coefficients; this packet does not instruct construction of a5 kW rig. Future validation begins with ambient low-energy water |

All listed future channels need sensor range, reference calibration, uncertainty,
sample latency and whole-run capture defined before physical validation.

## Universal mounting fixture

[Dimensioned Rev A drawing](../../hardware/breadboard_plate.svg) and
[OpenSCAD source](../../hardware/breadboard_plate.scad) describe a planned
180 ×120 ×3 mm breadboard plate. They intentionally use a universal strap mount
rather than unverified Pico PCB hole dimensions. The100 ×70 mm breadboard fit
envelope is an assumed maximum; measure the actual breadboard before fabrication.
The OpenSCAD source has not been rendered by a CAD tool in this milestone.

| Item | Planned choice | Rationale / tolerance intent |
| --- | --- | --- |
| Plate | 3 mm birch plywood,180 ×120 mm, R6 corners | Accessible sheet stock, electrical stand-off support. Stock thickness3 ±0.3 mm assumed, outer dimensions±0.5 mm design intent; actual manufacturing accuracy unmeasured |
| Strap slots | Six20 ×4 mm slots, R2 ends | Breadboard-retention slots centre(20,35),(160,35),(20,85),(160,85); cable tie centres(70,12),(110,12), origin top-left. Width4 +0.5/−0 mm intent; make a slot coupon first |
| Retention | Two nonconductive hook/loop straps, nominal3 mm width | Pass under/around breadboard base; no strap over Pico components, headers, buttons or USB shell. Measure actual strap fit |
| Feet | Four adhesive insulating feet,≥5 mm underside clearance | Keeps straps off desktop. Verify adhesion/stability after assembly |
| Cable route | USB exits upper edge through central corridor; loose service loop | Keep BOOTSEL/debug access visible; strain relief acts on cable jacket, never connector shell |

Assembly sequence: measure and photograph the actual breadboard and headers;
confirm slot coupon clearance; fabricate/deburr the unpowered plate; fit feet and
straps; insert the Pico on the breadboard with USB facing the corridor; inspect
underside strap clearance and all GPIO/BOOTSEL access; route cable with a service
loop; record fit. No fabrication has occurred. If the physical envelope does not
fit, revise the authored dimension rather than claiming the drawing was verified.

## Planned H1 acquisition checklist

1. Record date, operator, board model/marking, firmware mode and immutable
   ELF/UF2 hashes, compiler/SDK revisions, photograph of unpowered wiring,
   DMM identity/reference, Windows serial-port identity and capture command.
2. Measure3V3 and knob endpoints independently; record voltage values and ADC
   integer readings with uncertainties. Voltage→level remains emulation. Save
   unedited raw serial bytes and separate operator-event notes, not screenshots
   alone. Capture local device D and host wall clocks separately.
3. Boot with ARM held: verify DISARMED; release then explicitly press ARM with
   fresh valid inputs and trip cleared. Sweep the knob slowly and compare X ADC
   source/receipt diagnostics with independent voltage observations.
4. Remove GP14-to-GND jumper: capture separate-trip, heat/pump requests for
   tank topology and latching. Reconnect jumper; confirm no automatic rearm;
   RESET then separate ARM. Photograph actual wiring and state indication.
5. Capture N tick/overrun/drop/rejection counters under normal traffic and a
   bounded serial stress; retained counters/time intervals describe observed
   behavior only for the recorded configuration, not hard real-time assurance.
6. Watchdog exercise requires a separately reviewed explicit fault-injection
   build that stops completing scheduled work. Save that build's hash and raw
   reboot/reset-cause evidence; ordinary uptime cannot demonstrate watchdog
   reset. Do not infer a measured1500 ms delay from its configured value.
7. Inspect USB disconnect/reconnect and new-session intentional ARM. Archive
   raw capture, event notes, hashes, photos and actual failures. Record one real
   fit/assembly issue, hypotheses, discriminating observation, correction and
   retest. Status changes only after those artifacts exist.

H2 remains separate: ambient-water whole-run calibration followed by independent
holdout experiments. The emulation demonstration cannot validate the tank or
thermal physical equations or establish safety certification.
