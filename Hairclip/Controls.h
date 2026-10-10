#pragma once
#include <stdint.h>

constexpr uint32_t BUTTON_DEBOUNCE_MS = 35;
constexpr uint32_t LONG_PRESS_MS = 200;
constexpr uint32_t BRIGHTNESS_REPEAT_MS = 60;

enum class ButtonAction { None, ShortPress, BrightnessStep };

// Pure input logic: reading == true means the active-low button is pressed.
struct ButtonState {
  int pin;
  int direction;
  bool lastReading = false;
  bool pressed = false;
  bool longPressHandled = false;
  uint32_t lastChange = 0;
  uint32_t pressedAt = 0;
  uint32_t lastRepeatAt = 0;

  constexpr ButtonState(int buttonPin, int buttonDirection)
      : pin(buttonPin), direction(buttonDirection) {}

  constexpr void begin(bool reading, uint32_t now) {
    lastReading = pressed = reading;
    lastChange = pressedAt = lastRepeatAt = now;
    longPressHandled = false;
  }

  constexpr ButtonAction update(bool reading, uint32_t now) {
    if (reading != lastReading) {
      lastChange = now;
      lastReading = reading;
    }

    if (now - lastChange >= BUTTON_DEBOUNCE_MS && reading != pressed) {
      pressed = reading;
      if (pressed) {
        pressedAt = now;
        lastRepeatAt = now;
        longPressHandled = false;
      } else if (!longPressHandled) {
        return ButtonAction::ShortPress;
      }
    }

    // The first hold action runs once; later actions depend only on lastRepeatAt.
    // Checking elapsed == LONG_PRESS_MS here repeats on every loop in that ms.
    if (pressed && reading && now - pressedAt >= LONG_PRESS_MS
        && (!longPressHandled || now - lastRepeatAt >= BRIGHTNESS_REPEAT_MS)) {
      longPressHandled = true;
      lastRepeatAt = now;
      return ButtonAction::BrightnessStep;
    }
    return ButtonAction::None;
  }
};
