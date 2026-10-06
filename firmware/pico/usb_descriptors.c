/* Pico SDK CDC VID/PID and TinyUSB descriptor macros; upstream licenses retained
 * in THIRD_PARTY_LICENSES.txt. Device descriptor is for the indicator-only bench. */
#include "tusb.h"
#include "pico/unique_id.h"
#include <string.h>
static const tusb_desc_device_t device={
    .bLength=sizeof(tusb_desc_device_t), .bDescriptorType=TUSB_DESC_DEVICE,
    .bcdUSB=0x0200, .bDeviceClass=TUSB_CLASS_MISC, .bDeviceSubClass=MISC_SUBCLASS_COMMON,
    .bDeviceProtocol=MISC_PROTOCOL_IAD, .bMaxPacketSize0=CFG_TUD_ENDPOINT0_SIZE,
    .idVendor=0x2e8a, .idProduct=0x000a, .bcdDevice=0x0100,
    .iManufacturer=1, .iProduct=2, .iSerialNumber=3, .bNumConfigurations=1
};
enum { CONFIG_LENGTH=TUD_CONFIG_DESC_LEN+TUD_CDC_DESC_LEN };
static const uint8_t configuration[]={
    TUD_CONFIG_DESCRIPTOR(1,2,0,CONFIG_LENGTH,0,100),
    TUD_CDC_DESCRIPTOR(0,4,0x81,8,0x02,0x82,64)
};
const uint8_t *tud_descriptor_device_cb(void) { return (const uint8_t*)&device; }
const uint8_t *tud_descriptor_configuration_cb(uint8_t index) { (void)index; return configuration; }
const uint16_t *tud_descriptor_string_cb(uint8_t index,uint16_t langid) {
    static uint16_t encoded[40]; static char serial[PICO_UNIQUE_BOARD_ID_SIZE_BYTES*2+1];
    const char *text; size_t count,i; (void)langid;
    if(index==0u) { encoded[0]=(uint16_t)((TUSB_DESC_STRING<<8u)|4u); encoded[1]=0x0409; return encoded; }
    if(index==1u) text="Walter Teitelbaum";
    else if(index==2u) text="Virtual Thermal Fluid Lab";
    else if(index==3u) { if(serial[0]=='\0') pico_get_unique_board_id_string(serial,sizeof(serial)); text=serial; }
    else if(index==4u) text="Evidence CDC"; else return NULL;
    count=strlen(text); if(count>39u) count=39u;
    for(i=0u;i<count;i++) encoded[i+1u]=(uint8_t)text[i];
    encoded[0]=(uint16_t)((TUSB_DESC_STRING<<8u)|(2u*count+2u)); return encoded;
}
