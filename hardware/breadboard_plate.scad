// Planned universal breadboard/board-emulation plate. Units: mm.
// NOT_FABRICATED; no Pico PCB hole dimensions or fitted hardware are asserted.
// Project-authored MIT design. Render/export requires a separately installed
// OpenSCAD; no CAD render or manufacturing action is claimed by this source.
plate_length_mm = 180;
plate_width_mm = 120;
plate_thickness_mm = 3;
corner_radius_mm = 6;
slot_length_mm = 20;
slot_width_mm = 4;

module rounded_rectangle(length_mm, width_mm, radius_mm) {
    hull() for (x=[radius_mm,length_mm-radius_mm])
        for(y=[radius_mm,width_mm-radius_mm])
            translate([x,y]) circle(r=radius_mm,$fn=48);
}
module strap_slot(x_mm,y_mm) {
    // Drawing coordinates start at the top-left; CAD XY starts bottom-left.
    translate([x_mm,plate_width_mm-y_mm]) hull()
        for(y=[-(slot_length_mm-slot_width_mm)/2,(slot_length_mm-slot_width_mm)/2])
            translate([0,y]) circle(r=slot_width_mm/2,$fn=32);
}
linear_extrude(height=plate_thickness_mm)
    difference() {
        rounded_rectangle(plate_length_mm,plate_width_mm,corner_radius_mm);
        for(x=[20,160]) for(y=[35,85]) strap_slot(x,y);
        // Optional cable strain-relief tie; no force is transferred to USB shell.
        for(x=[70,110]) strap_slot(x,12);
    }
