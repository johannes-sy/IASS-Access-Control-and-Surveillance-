# Native (x86) build of the protocol/dispatch/handler layer against test
# mocks, for real functional testing without AVR hardware. Not part of the
# firmware build -- run with `make -C tests/native`.
CC := gcc
CFLAGS := -std=c11 -Wall -Wextra -g -I../.. -I../../include
SRCS := test_dispatch.c mock_drivers.c mock_servo.c \
	../../protocol/frame.c ../../protocol/payload.c ../../protocol/command_dispatch.c \
	../../handlers/handlers.c ../../handlers/system_handlers.c ../../handlers/servo_handlers.c \
	../../handlers/door_handlers.c ../../handlers/alarm_handlers.c \
	../../actuators/door_lock.c ../../actuators/alarm.c \
	../../system/state.c ../../system/state_watch.c

BUILD := build

.PHONY: all run clean
all: $(BUILD)/native_test

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/native_test: $(SRCS) | $(BUILD)
	$(CC) $(CFLAGS) $(SRCS) -o $@

run: $(BUILD)/native_test
	./$(BUILD)/native_test

clean:
	rm -rf $(BUILD)
