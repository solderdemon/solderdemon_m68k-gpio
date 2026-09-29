#include <stdio.h>
#include "gpio.h"

/* Run with nothing plugged into J2/J3: the self-test drives every pin. */
int main(void)
{
    uint32_t bad = gpio_selftest();
    printf("GPIO card at $%06lX: self-test %s", GPIO_CARD_BASE, bad ? "FAILED" : "OK\n");
    if (bad) {
        printf(", bad pins %08lX\n", (unsigned long)bad);
        return 1;
    }

    printf("Inputs D..A: %08lX\n", (unsigned long)gpio_read());
    puts("Drive A0 (J2.1) high: gpio_config(GPIO_DIR_A, 0x00000001);");
    return 0;
}
