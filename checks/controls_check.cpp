// Compile with: g++ -std=c++17 -fsyntax-only checks/controls_check.cpp
// static_assert runs the real Controls.h logic at compile time, even with
// the ESP32 cross compiler: no host compiler or board is needed.
#include "../Hairclip/Controls.h"

constexpr bool repeatedTimestamp() {
  ButtonState button(14, 1);
  button.begin(false, 0);
  if (button.update(true, 10) != ButtonAction::None) return false;
  if (button.update(true, 45) != ButtonAction::None) return false;
  const uint32_t firstStep = 45 + LONG_PRESS_MS;
  if (button.update(true, firstStep - 1) != ButtonAction::None) return false;

  int steps = 0;
  for (int i = 0; i < 1000; ++i) {
    if (button.update(true, firstStep) == ButtonAction::BrightnessStep) ++steps;
  }
  if (steps != 1) return false;
  if (button.update(true, firstStep + BRIGHTNESS_REPEAT_MS - 1) != ButtonAction::None) return false;
  for (int i = 0; i < 1000; ++i) {
    if (button.update(true, firstStep + BRIGHTNESS_REPEAT_MS) == ButtonAction::BrightnessStep) ++steps;
  }
  return steps == 2;
}

constexpr bool tapWithBounce() {
  ButtonState button(0, -1);
  button.begin(false, 0);
  button.update(true, 10);
  button.update(false, 20);
  button.update(true, 30);
  if (button.update(true, 64) != ButtonAction::None || button.pressed) return false;
  if (button.update(true, 65) != ButtonAction::None || !button.pressed) return false;
  if (button.update(false, 140) != ButtonAction::None) return false;
  if (button.update(false, 174) != ButtonAction::None) return false;
  if (button.update(false, 175) != ButtonAction::ShortPress) return false;
  return button.update(false, 175) == ButtonAction::None && button.direction == -1;
}

constexpr bool releaseStopsRepeats() {
  ButtonState button(14, 1);
  button.begin(true, 0);
  if (button.update(true, LONG_PRESS_MS) != ButtonAction::BrightnessStep) return false;
  // Release at the next repeat deadline: do not change brightness during debounce.
  const uint32_t releasedAt = LONG_PRESS_MS + BRIGHTNESS_REPEAT_MS;
  if (button.update(false, releasedAt) != ButtonAction::None) return false;
  if (button.update(false, releasedAt + BUTTON_DEBOUNCE_MS) != ButtonAction::None) return false;
  // A completed long press must not also switch the scene on release.
  return button.update(false, 1000) == ButtonAction::None;
}

constexpr bool irregularPollingAndStartup() {
  ButtonState button(14, 1);
  button.begin(true, 30000);
  if (button.update(true, 30000) != ButtonAction::None) return false;
  if (button.update(true, 30000 + LONG_PRESS_MS - 1) != ButtonAction::None) return false;
  // The loop can skip the exact hold threshold without losing the first step.
  const uint32_t firstStep = 30000 + LONG_PRESS_MS + 17;
  if (button.update(true, firstStep) != ButtonAction::BrightnessStep) return false;
  if (button.update(true, firstStep + BRIGHTNESS_REPEAT_MS - 1) != ButtonAction::None) return false;
  return button.update(true, firstStep + BRIGHTNESS_REPEAT_MS) == ButtonAction::BrightnessStep;
}

constexpr bool clockRollover() {
  ButtonState button(14, 1);
  const uint32_t start = UINT32_MAX - 100;
  button.begin(true, start);
  if (button.update(true, start + LONG_PRESS_MS - 1) != ButtonAction::None) return false;
  if (button.update(true, start + LONG_PRESS_MS) != ButtonAction::BrightnessStep) return false;
  if (button.update(true, start + LONG_PRESS_MS + BRIGHTNESS_REPEAT_MS - 1) != ButtonAction::None) return false;
  return button.update(true, start + LONG_PRESS_MS + BRIGHTNESS_REPEAT_MS) == ButtonAction::BrightnessStep;
}

constexpr bool steadyHoldRate() {
  ButtonState button(14, 1);
  button.begin(true, 0);
  int steps = 0;
  for (uint32_t now = 0; now <= 2000; ++now) {
    for (int poll = 0; poll < 16; ++poll) {
      if (button.update(true, now) == ButtonAction::BrightnessStep) ++steps;
    }
  }
  return steps == 1 + (2000 - LONG_PRESS_MS) / BRIGHTNESS_REPEAT_MS;
}

static_assert(repeatedTimestamp(), "Multiple brightness steps in one millisecond");
static_assert(tapWithBounce(), "A debounced tap must switch the scene once");
static_assert(releaseStopsRepeats(), "Release must stop the hold without a scene change");
static_assert(irregularPollingAndStartup(), "Hold timing must start from the press");
static_assert(clockRollover(), "Hold timing must survive millis() rollover");
static_assert(steadyHoldRate(), "Hold repeat rate must not depend on polling frequency");
