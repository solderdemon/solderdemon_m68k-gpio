#include <stdint.h>
#include <basicio.h>
#define REG8(addr) (*(volatile uint8_t *)(addr))
int kmain(void)
{
    REG8(0xf40005UL) = 0;
    REG8(0xf40001UL) = 0;
    REG8(0xf40003UL) = 0;
    REG8(0xf40007UL) = 0;
    REG8(0xf40009UL) = 0;
    REG8(0xf40005UL) = 0x0f;
    println("GPIO A-D LOW. Press a key to release.");
    while (!checkchar()) { }
    readchar();
    REG8(0xf40005UL) = 0;
    return 0;
}
