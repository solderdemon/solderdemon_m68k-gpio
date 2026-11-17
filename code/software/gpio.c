#include "gpio.h"

#ifdef GPIO_HOST_TEST
void gpio_hw_write(unsigned reg, uint8_t v);
uint8_t gpio_hw_read(unsigned reg);
#else
static inline void gpio_hw_write(unsigned reg, uint8_t v) { *(volatile uint8_t *)(GPIO_CARD_BASE + reg) = v; }
static inline uint8_t gpio_hw_read(unsigned reg) { return *(volatile uint8_t *)(GPIO_CARD_BASE + reg); }
#endif

static const uint8_t port_reg[4] = { GPIO_REG_A, GPIO_REG_B, GPIO_REG_C, GPIO_REG_D };

/* The direction register cannot be read back; the latches can't either (reads return the pins). */
static uint32_t latch;
static uint8_t dir;

void gpio_write(uint32_t value)
{
    latch = value;
    for (unsigned p = 0; p < 4; p++)
        gpio_hw_write(port_reg[p], (uint8_t)(value >> (8 * p)));
}

void gpio_config(uint8_t ports, uint32_t value)
{
    gpio_write(value);
    dir = ports & GPIO_DIR_ALL;
    gpio_hw_write(GPIO_REG_DIR, dir);
}

void gpio_init(void) { gpio_config(0, 0); }

uint8_t gpio_dir(void) { return dir; }
uint32_t gpio_latch(void) { return latch; }

uint32_t gpio_read(void)
{
    uint32_t v = 0;
    for (unsigned p = 0; p < 4; p++)
        v |= (uint32_t)gpio_hw_read(port_reg[p]) << (8 * p);
    return v;
}

void gpio_write_pin(unsigned pin, bool level)
{
    if (pin >= GPIO_PINS) return;
    gpio_write(level ? latch | 1UL << pin : latch & ~(1UL << pin));
}

bool gpio_read_pin(unsigned pin) { return pin < GPIO_PINS && (gpio_read() >> pin & 1); }

void gpio_write_port(unsigned port, uint8_t value)
{
    if (port >= 4) return;
    latch = (latch & ~(0xFFUL << (8 * port))) | (uint32_t)value << (8 * port);
    gpio_hw_write(port_reg[port], value);
}

uint8_t gpio_read_port(unsigned port) { return port < 4 ? gpio_hw_read(port_reg[port]) : 0xFF; }

uint32_t gpio_selftest(void)
{
    /* Solid, alternating, and a different byte per port so a decoding fault that mirrors ports shows up. */
    static const uint32_t pattern[] = { 0x00000000UL, 0xFFFFFFFFUL, 0x55555555UL, 0xAAAAAAAAUL, 0x11223344UL, 0xEEDDCCBBUL };
    uint32_t bad = 0;

    gpio_init();
    bad |= ~gpio_read();                               /* inputs: RN1..RN4 pull everything high */
    for (unsigned i = 0; i < sizeof pattern / sizeof pattern[0]; i++) {
        gpio_config(GPIO_DIR_ALL, pattern[i]);
        bad |= gpio_read() ^ pattern[i];
    }
    for (unsigned p = 0; p < 4; p++) {                 /* each port's direction bit on its own */
        uint32_t mask = 0xFFUL << (8 * p);
        gpio_config((uint8_t)(1 << p), 0);
        bad |= gpio_read() ^ ~mask;
    }
    gpio_init();
    return bad;
}
