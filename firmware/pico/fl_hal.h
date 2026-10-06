#ifndef FL_HAL_H
#define FL_HAL_H
#include <stdbool.h>
#include <stdint.h>
#include "fl_core.h"
#define FL_ADC_PIN 26u
#define FL_TRIP_PIN 14u
#define FL_ARM_PIN 15u
#define FL_RESET_PIN 16u
#define FL_LED_PIN 25u
#define FL_WATCHDOG_MS 1500u
void fl_hal_init(void);
bool fl_hal_adc(uint16_t *raw);
bool fl_hal_trip(void);
bool fl_hal_arm_pressed(void);
bool fl_hal_reset_pressed(void);
void fl_hal_indicator(fl_state state,uint64_t local_now_us);
#endif
