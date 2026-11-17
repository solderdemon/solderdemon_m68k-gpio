/* Blink an LED connected through 1 kOhm from +5V to J3 D7. */
#include <stdint.h>
#include <basicio.h>
#define PORT_D (*(volatile uint8_t *)0xF40009UL)
#define DIR (*(volatile uint8_t *)0xF40005UL)
int kmain(void)
{
    DIR = 0;
    PORT_D = 0xff;
    DIR = 8;
    println("D7 LED blink: press a key to exit");
    while (!checkchar()) {
        PORT_D = 0x7f;  /* D7 low: LED on */
        delay(250000);
        PORT_D = 0xff;  /* D7 high: LED off */
        delay(250000);
    }
    readchar();
    DIR = 0;
    return 0;
}
