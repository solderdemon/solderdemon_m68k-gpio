/*
 * SolderDemon m68k GPIO card r1 driver, 32 pins.
 *
 * Byte registers (byte access only, window $F40000-$F41FFF, repeating every 16 bytes):
 *   $F40001  port A   write: output latch   read: pin levels
 *   $F40003  port B
 *   $F40005  direction, write-only: b0 A  b1 B  b2 C  b3 D; 1 = output
 *   $F40007  port C
 *   $F40009  port D
 * System reset clears the direction register: every pin is an input, pulled up to 5 V.
 * The 74HCT574 latches power up with random contents.
 * Pin bit n: 0..7 A0..A7 (J2 1..8), 8..15 B0..B7 (J2 9..16),
 *            16..23 C0..C7 (J3 1..8), 24..31 D0..D7 (J3 9..16).
 */
#ifndef SOLDERDEMON_GPIO_H
#define SOLDERDEMON_GPIO_H

#include <stdbool.h>
#include <stdint.h>

#define GPIO_CARD_BASE 0xF40001UL
#define GPIO_REG_A     0   /* offsets from GPIO_CARD_BASE */
#define GPIO_REG_B     2
#define GPIO_REG_DIR   4
#define GPIO_REG_C     6
#define GPIO_REG_D     8

#define GPIO_PINS      32

/* Direction: each bit switches a whole 8-pin port between input and output. */
#define GPIO_DIR_A     0x01
#define GPIO_DIR_B     0x02
#define GPIO_DIR_C     0x04
#define GPIO_DIR_D     0x08
#define GPIO_DIR_ALL   0x0F

/* All pins inputs, all latches 0. */
void gpio_init(void);

/* Loads the output latches first, then enables the selected ports, so outputs never glitch. */
void gpio_config(uint8_t dir, uint32_t value);
uint8_t gpio_dir(void);

void gpio_write(uint32_t value);
uint32_t gpio_latch(void);            /* last value written */
uint32_t gpio_read(void);             /* real pin levels, outputs included */
void gpio_write_pin(unsigned pin, bool level);
bool gpio_read_pin(unsigned pin);

/* One 8-bit port (0..3 = A..D) on its own: a single register access, the other ports untouched.
 * The write updates the latch copy that gpio_write_pin() and gpio_latch() use. */
void gpio_write_port(unsigned port, uint8_t value);
uint8_t gpio_read_port(unsigned port);

/* Drives EVERY pin with test patterns: disconnect J2 and J3 first. Returns a mask of failed
 * pins (0 = card OK), and leaves the card in the gpio_init() state. */
uint32_t gpio_selftest(void);

#endif
