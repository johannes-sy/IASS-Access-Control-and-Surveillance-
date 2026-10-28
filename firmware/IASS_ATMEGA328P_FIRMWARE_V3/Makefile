MCU       := atmega328p
F_CPU     := 16000000UL
PROGRAMMER:= arduino
PORT      ?= /dev/ttyUSB0
BAUD      := 115200

CC        := avr-gcc
OBJCOPY   := avr-objcopy
SIZE      := avr-size
AVRDUDE   := avrdude

CFLAGS    := -std=c11 -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Os -Wall -Wextra -Wshadow -Wconversion -ffunction-sections -fdata-sections
LDFLAGS   := -mmcu=$(MCU) -Wl,--gc-sections
INCLUDES  := -Iinclude -I.

TARGET    := iass_atmega328p
BUILD     := build

SRCS := \
	main.c \
	drivers/gpio.c \
	drivers/uart.c \
	drivers/timer.c \
	drivers/interrupts.c \
	protocol/frame.c \
	protocol/payload.c \
	protocol/command_dispatch.c \
	handlers/handlers.c \
	handlers/system_handlers.c \
	handlers/servo_handlers.c \
	handlers/door_handlers.c \
	handlers/alarm_handlers.c \
	actuators/servo.c \
	actuators/door_lock.c \
	actuators/alarm.c \
	system/watchdog.c \
	system/state.c \
	system/state_watch.c

OBJS := $(SRCS:%.c=$(BUILD)/%.o)

.PHONY: all clean flash size info

all: $(BUILD)/$(TARGET).hex

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: %.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJS)
	$(CC) $(LDFLAGS) $^ -o $@
	$(SIZE) $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

size: $(BUILD)/$(TARGET).elf
	$(SIZE) -C --mcu=$(MCU) $<

flash: $(BUILD)/$(TARGET).hex
	$(AVRDUDE) -p m328p -c $(PROGRAMMER) -P $(PORT) -b $(BAUD) -U flash:w:$<:i

info:
	@echo "MCU=$(MCU) F_CPU=$(F_CPU) BAUD=$(BAUD) PORT=$(PORT)"

clean:
	rm -rf $(BUILD)
