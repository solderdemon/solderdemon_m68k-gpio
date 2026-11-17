/* DHT22/AM2302 on SolderDemon GPIO J3.16 (D7). See README.md. */
#include <stdint.h>
#include <basicio.h>

#define PORT_D (*(volatile uint8_t *)0xF40009UL)
#define DIR    (*(volatile uint8_t *)0xF40005UL)
#define DATA   0x80u
#define TIMEOUT 1000u

/* The same polling loop measures both parts of a bit; comparing their lengths
 * avoids a CPU-clock-specific microsecond delay. The 50 us low pulse lies
 * between the 22-30 us zero and the 68-75 us one high pulse. */
static unsigned pulse(unsigned level)
{
    unsigned n = 0;
    while (((PORT_D & DATA) != 0) == (level != 0)) {
        if (++n == TIMEOUT) return TIMEOUT;
    }
    return n;
}

static unsigned failed_stage, failed_bit, idle_level, driven_level;

static int read_sensor(uint8_t data[5])
{
    unsigned low[40], high[40];
    uint16_t saved_sr;
    for (unsigned i = 0; i < 5; ++i) data[i] = 0;

    /* Port D only: preload zero, then drive low. Never drive the bus high. */
    DIR = 0;
    idle_level = (PORT_D & DATA) != 0;
    PORT_D = 0;
    DIR = 8;
    driven_level = (PORT_D & DATA) != 0;
    delay(1000);                  /* approximately 2 ms at 10 MHz */
    __asm__ volatile ("move.w %%sr,%0\n\tori.w #0x0700,%%sr"
                      : "=d" (saved_sr) : : "cc", "memory");
    DIR = 0;                      /* release; pull-ups provide high */

    failed_stage = 1;
    if (pulse(1) == TIMEOUT) goto timeout;
    failed_stage = 2;
    if (pulse(0) == TIMEOUT) goto timeout;
    failed_stage = 3;
    if (pulse(1) == TIMEOUT) goto timeout;
    failed_stage = 4;
    for (unsigned bit = 0; bit < 40; ++bit) {
        failed_bit = bit;
        low[bit] = pulse(0);
        if (low[bit] == TIMEOUT) goto timeout;
        high[bit] = pulse(1);
        if (high[bit] == TIMEOUT) goto timeout;
    }
    __asm__ volatile ("move.w %0,%%sr" : : "d" (saved_sr) : "cc", "memory");
    for (unsigned bit = 0; bit < 40; ++bit)
        data[bit / 8] = (uint8_t)((data[bit / 8] << 1) | (high[bit] > low[bit]));
    if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4]) return 2;
    return 0;

timeout:
    __asm__ volatile ("move.w %0,%%sr" : : "d" (saved_sr) : "cc", "memory");
    return 1;
}

static void print_decimal(unsigned value)
{
    char buf[10];
    unsigned n = 0;
    do { buf[n++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (n) printchar(buf[--n]);
}

static void print_tenths(unsigned value)
{
    print_decimal(value / 10);
    printchar('.');
    printchar((char)('0' + value % 10));
}

int kmain(void)
{
    uint8_t data[5];
    DIR = 0;
    println("DHT22 room monitor");
    mcDelaymsec10(300);           /* DHT22: allow 3 s to settle */
    while (!checkchar()) {
        int error = read_sensor(data);
        if (error == 1) {
            print("Sensor timeout, stage ");
            print_decimal(failed_stage);
            if (failed_stage == 4) { print(", bit "); print_decimal(failed_bit); }
            print("; idle="); print_decimal(idle_level);
            print(" driven="); print_decimal(driven_level);
            println("; retrying.");
        }
        else if (error == 2) println("Sensor checksum error; retrying.");
        else {
            unsigned h = ((unsigned)data[0] << 8) | data[1];
            unsigned t = ((unsigned)(data[2] & 0x7f) << 8) | data[3];
            print("Temperature: ");
            if (data[2] & 0x80) print("-");
            print_tenths(t);
            print(" C   Humidity: ");
            print_tenths(h);
            println(" % RH");
        }
        mcDelaymsec10(300);       /* at least 3 s between requests */
    }
    readchar();
    DIR = 0;
    return 0;
}
