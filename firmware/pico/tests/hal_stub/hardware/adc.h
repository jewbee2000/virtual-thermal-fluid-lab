#ifndef FL_REVIEW_ADC_H
#define FL_REVIEW_ADC_H
#include <stdint.h>
typedef struct {volatile uint32_t cs,result;} fl_review_adc_hw;
extern fl_review_adc_hw fl_review_adc;
#define adc_hw (&fl_review_adc)
#define ADC_CS_START_ONCE_BITS UINT32_C(4)
#define ADC_CS_READY_BITS UINT32_C(256)
#define ADC_CS_ERR_BITS UINT32_C(512)
#define ADC_CS_ERR_STICKY_BITS UINT32_C(1024)
static inline void adc_init(void) {}
static inline void adc_gpio_init(unsigned pin) {(void)pin;}
static inline void adc_select_input(unsigned pin) {(void)pin;}
void hw_set_bits(volatile uint32_t *address,uint32_t bits);
#endif
