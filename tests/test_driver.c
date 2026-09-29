/* Host test: the real gpio.c against a model of the card: four 74HCT574 latches with
 * tri-state outputs, the 74HCT175 direction register, 74HCT541 read-back and the
 * RN1..RN4 pull-ups, with optional external signals on J2/J3. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "gpio.h"

static uint8_t lat[4], dirreg;
static uint32_t ext_mask, ext_val;      /* pins driven from outside */
static uint32_t stuck_mask, stuck_val;  /* simulated board faults */
static long writes, glitches;

static uint32_t port_mask(uint8_t ports)
{
    uint32_t m = 0;
    for (int p = 0; p < 4; p++)
        if (ports >> p & 1) m |= 0xFFUL << (8 * p);
    return m;
}

static uint32_t pins(void)
{
    uint32_t oe = port_mask(dirreg), latch = 0;
    for (int p = 0; p < 4; p++) latch |= (uint32_t)lat[p] << (8 * p);
    assert(!(oe & ext_mask));                                   /* never fight an external driver */
    uint32_t v = (latch & oe) | (ext_val & ext_mask) | ~(oe | ext_mask);
    return (v & ~stuck_mask) | (stuck_val & stuck_mask);
}

static int port_of(unsigned reg)
{
    switch (reg) {
    case GPIO_REG_A: return 0;
    case GPIO_REG_B: return 1;
    case GPIO_REG_C: return 2;
    case GPIO_REG_D: return 3;
    default: return -1;
    }
}

void gpio_hw_write(unsigned reg, uint8_t v)
{
    writes++;
    if (reg == GPIO_REG_DIR) {
        uint32_t before = pins();
        uint8_t old = dirreg;
        dirreg = v & 0x0F;                                      /* 74HCT175 stores D0..D3 only */
        /* A port that was already an output must not change level just because DIR was rewritten. */
        if ((before ^ pins()) & port_mask(old & dirreg)) glitches++;
        return;
    }
    int p = port_of(reg);
    assert(p >= 0 && "write outside the five registers");
    lat[p] = v;
}

uint8_t gpio_hw_read(unsigned reg)
{
    int p = port_of(reg);
    assert(p >= 0 && "read of a write-only or unused address");
    return (uint8_t)(pins() >> (8 * p));
}

int main(void)
{
    /* Power-up: /RESET clears the direction register; the 574 latches hold garbage. */
    lat[0] = 0x3C; lat[1] = 0xC3; lat[2] = 0x5A; lat[3] = 0xA5; dirreg = 0;
    assert(pins() == 0xFFFFFFFFUL);

    gpio_init();
    assert(dirreg == 0 && !lat[0] && !lat[1] && !lat[2] && !lat[3]);

    /* Self-test on a good card with nothing connected. */
    assert(gpio_selftest() == 0);
    assert(dirreg == 0 && !lat[0] && !lat[1] && !lat[2] && !lat[3]);

    /* Self-test finds a pin shorted to GND and one shorted to 5 V, on both connectors. */
    stuck_mask = 0x01000100UL; stuck_val = 0x01000000UL;
    assert(gpio_selftest() == 0x01000100UL);
    stuck_mask = 0;

    /* Inputs from outside. */
    ext_mask = 0xFFFFFFFFUL; ext_val = 0xCAFE1234UL;
    assert(gpio_read() == 0xCAFE1234UL);
    assert(gpio_read_pin(2) && !gpio_read_pin(0) && gpio_read_pin(31) && !gpio_read_pin(32));

    /* Ports A and C outputs, B and D still driven externally. */
    ext_mask = 0xFF00FF00UL;
    gpio_config(GPIO_DIR_A | GPIO_DIR_C, 0x00770005UL);
    assert(dirreg == 0x05 && gpio_dir() == (GPIO_DIR_A | GPIO_DIR_C));
    assert(gpio_read() == ((0xCAFE1234UL & 0xFF00FF00UL) | 0x00770005UL));
    gpio_write_pin(1, true);
    gpio_write_pin(0, false);
    gpio_write_pin(23, true);
    assert((gpio_read() & 0x00FF00FFUL) == 0x00F70006UL && gpio_latch() == 0x00F70006UL);

    /* Latched value is ready before the outputs turn on. */
    ext_mask = 0;
    gpio_config(GPIO_DIR_ALL, 0xDEADBEEFUL);
    assert(gpio_read() == 0xDEADBEEFUL);
    gpio_config(GPIO_DIR_ALL, 0xDEADBEEFUL);                    /* rewrite without a change */
    gpio_config(GPIO_DIR_D | GPIO_DIR_B, 0xDEADBEEFUL);
    assert(gpio_read() == 0xDEFFBEFFUL);                        /* released ports float high */
    assert(glitches == 0);

    /* Single-port access: one register, the other latches and the shadow copy stay consistent. */
    gpio_config(GPIO_DIR_ALL, 0x11223344UL);
    long w0 = writes;
    gpio_write_port(2, 0xA5);
    assert(writes == w0 + 1 && gpio_latch() == 0x11A53344UL && gpio_read() == 0x11A53344UL);
    assert(gpio_read_port(2) == 0xA5 && gpio_read_port(0) == 0x44 && gpio_read_port(4) == 0xFF);
    gpio_write_port(4, 0x00);                                   /* out of range: ignored */
    assert(writes == w0 + 1);
    gpio_write_pin(0, true);                                    /* later pin writes keep port C */
    assert(gpio_read() == 0x11A53345UL);

    gpio_init();
    assert(dirreg == 0 && pins() == 0xFFFFFFFFUL);

    printf("PASS: real C driver, 32 pins, %ld register writes\n", writes);
    return 0;
}
