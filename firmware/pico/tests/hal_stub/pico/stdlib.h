#ifndef FL_REVIEW_STDLIB_H
#define FL_REVIEW_STDLIB_H
#include <stdint.h>
#include <stdbool.h>
#define GPIO_IN 0
#define GPIO_OUT 1
uint64_t time_us_64(void);
void tight_loop_contents(void);
static inline void gpio_init(unsigned pin) {(void)pin;}
static inline void gpio_set_dir(unsigned pin,unsigned direction) {(void)pin;(void)direction;}
static inline void gpio_pull_up(unsigned pin) {(void)pin;}
static inline void gpio_put(unsigned pin,bool value) {(void)pin;(void)value;}
static inline bool gpio_get(unsigned pin) {(void)pin;return false;}
#endif
