SOLDERDEMON_M68K_DIR?=../../../solderdemon_m68k
# The SolderDemon m68k SDK (software.mk) is rosco_m68k compatible and keeps the upstream variable name.
ifndef ROSCO_M68K_DIR
ROSCO_M68K_DIR=$(SOLDERDEMON_M68K_DIR)
endif
include $(ROSCO_M68K_DIR)/code/software/software.mk

HOSTCC ?= clang
host-test: ../tests/test_driver.c gpio.c gpio.h
	mkdir -p ../build
	$(HOSTCC) -std=c99 -Wall -Wextra -DGPIO_HOST_TEST -I. ../tests/test_driver.c gpio.c -o ../build/test_driver
	../build/test_driver
