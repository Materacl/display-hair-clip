#define LILYGO_LGFX_USE_T_DISPLAY_S3
#include <LilyGo_LovyanGFX.h>
#include <math.h>
#include "Controls.h"
#include "AnimationAssets.h"

LilyGo_T_Display_S3 display;
LGFX_Sprite frame(&display);

constexpr int SCREEN_W = 320;
constexpr int SCREEN_H = 170;
constexpr int BUTTON_NEXT = 14;
constexpr int BUTTON_PREV = 0;
constexpr uint8_t SCENE_COUNT = 7;

ButtonState nextButton(BUTTON_NEXT, 1);
ButtonState prevButton(BUTTON_PREV, -1);
uint8_t scene = 0;
uint8_t brightness = 150;
uint32_t sceneStarted = 0;
uint32_t lastFrame = 0;
bool frameReady = false;
bool showBrightnessIndicator = false;
uint32_t brightnessChangedAt = 0;

constexpr uint8_t BRIGHTNESS_MIN = 20;
constexpr uint8_t BRIGHTNESS_MAX = 255;
constexpr uint8_t BRIGHTNESS_STEP = 4;
constexpr uint32_t PAGE_INDICATOR_MS = 1500;

uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return display.color565(r, g, b);
}

void drawHearts(uint32_t elapsed) {
  frame.fillScreen(rgb(8, 0, 12));
  for (int i = 0; i < 12; ++i) {
    const float glow = (sinf(elapsed * 0.0013f + i * 2.1f) + 1) * 0.5f;
    const int x = (i * 73 + 17) % SCREEN_W;
    const int y = (i * 47 + 19) % SCREEN_H;
    const uint16_t color = rgb(30 + glow * 65, 10 + glow * 30, 30 + glow * 50);
    frame.drawPixel(x, y, color);
    if (glow > 0.75f) {
      frame.drawFastHLine(x - 1, y, 3, color);
      frame.drawFastVLine(x, y - 1, 3, color);
    }
  }

  const int baseX[] = {18, 52, 85, 117, 153, 185, 220, 253, 286, 311, 72, 205};
  const uint8_t sizes[] = {5, 2, 6, 3, 7, 1, 4, 2, 5, 3, 0, 4};
  for (int i = 0; i < 12; ++i) {
    const float speed = 0.018f + sizes[i] * 0.003f + (i % 3) * 0.002f;
    const float travel = fmodf(elapsed * speed + i * 47.0f, SCREEN_H + 60.0f);
    const int y = SCREEN_H + 22 - static_cast<int>(travel);
    const int x = baseX[i] + static_cast<int>(sinf(elapsed * 0.0012f + i * 1.7f) * (5 + i % 4));
    drawAssetFrame(FLOATING_HEARTS, x - 22, y - 22, sizes[i] + (i % 4) * 8);
  }
}

void drawSceneDots() {
  for (uint8_t i = 0; i < SCENE_COUNT; ++i) {
    const int x = SCREEN_W / 2 - (SCENE_COUNT - 1) * 6 + i * 12;
    frame.fillCircle(x, 8, 2,
                     i == scene ? rgb(255, 255, 255) : rgb(72, 72, 72));
  }
}

const uint8_t *glyphRows(char letter) {
  static const uint8_t H[7] = {17, 17, 17, 31, 17, 17, 17};
  static const uint8_t U[7] = {17, 17, 17, 17, 17, 17, 14};
  static const uint8_t N[7] = {17, 25, 25, 21, 19, 19, 17};
  static const uint8_t G[7] = {14, 17, 16, 23, 17, 17, 14};
  static const uint8_t R[7] = {30, 17, 17, 30, 20, 18, 17};
  static const uint8_t Y[7] = {17, 17, 10, 4, 4, 4, 4};
  static const uint8_t F[7] = {31, 16, 16, 30, 16, 16, 16};
  static const uint8_t E[7] = {31, 16, 16, 30, 16, 16, 31};
  static const uint8_t D[7] = {30, 17, 17, 17, 17, 17, 30};
  switch (letter) {
    case 'H': return H;
    case 'U': return U;
    case 'N': return N;
    case 'G': return G;
    case 'R': return R;
    case 'Y': return Y;
    case 'F': return F;
    case 'E': return E;
    case 'D': return D;
    default: return D;
  }
}

void drawBigWord(const char *word, int x, int y, int cellW, int cellH,
                 int letterSpacing, uint16_t color) {
  int cursorX = x;
  while (*word) {
    if (*word == ' ') {
      cursorX += cellW * 2;
      ++word;
      continue;
    }
    const uint8_t *rows = glyphRows(*word++);
    for (int col = 0; col < 5; ++col) {
      const uint8_t mask = 1 << (4 - col);
      int row = 0;
      while (row < 7) {
        while (row < 7 && !(rows[row] & mask)) ++row;
        const int firstRow = row;
        while (row < 7 && (rows[row] & mask)) ++row;
        if (row > firstRow) {
          frame.fillRect(cursorX + col * cellW, y + firstRow * cellH,
                         cellW, (row - firstRow) * cellH, color);
        }
      }
    }
    cursorX += cellW * 5;
    if (*word && *word != ' ') cursorX += cellW + letterSpacing;
  }
}

void drawAssetFrame(const AnimationAsset &asset, int x, int y, uint16_t index) {
  uint32_t cursor = asset.offsets[index];
  for (int row = 0; row < asset.height; ++row) {
    int col = 0;
    while (col < asset.width) {
      const uint8_t length = asset.data[cursor++];
      const uint16_t color = asset.palette[asset.data[cursor++]];
      if (color) frame.drawFastHLine(x + col, y + row, length, color);
      col += length;
    }
  }
}

void drawAnimationFrame(const AnimationAsset &asset, int x, int y,
                        uint32_t elapsed, uint32_t period) {
  drawAssetFrame(asset, x, y, (elapsed % period) * asset.frameCount / period);
}

float equalizerLevel(float time, int bar) {
  const float swell = (sinf(time * 0.0037f + bar * 0.63f) + 1) * 0.5f;
  const float detail = (sinf(time * 0.0089f - bar * 1.31f) + 1) * 0.5f;
  const float envelope = (sinf(time * 0.0013f - bar * 0.21f) + 1) * 0.5f;
  return 2 + 5 * (0.50f * swell + 0.28f * detail + 0.22f * envelope);
}

void drawEqualizer(uint32_t elapsed) {
  static const uint8_t reds[16] = {20,20,20,30,40,60,85,115,145,175,205,230,250,255,255,255};
  static const uint8_t greens[16] = {235,225,210,190,165,140,115,90,70,55,45,40,45,60,80,105};
  static const uint8_t blues[16] = {190,210,235,255,255,255,255,255,255,255,250,230,210,185,155,135};
  constexpr int BASELINE = 158;
  constexpr int SEGMENTS = 7;
  frame.fillScreen(rgb(3, 4, 10));
  for (int i = 0; i < 16; ++i) {
    const int x = 1 + i * 20;
    const float level = equalizerLevel(elapsed, i);
    // A short decaying history makes peak motion independent of the frame rate.
    float peak = level;
    for (uint32_t age = 50; age <= 500 && age <= elapsed; age += 50) {
      const float previous = equalizerLevel(elapsed-age, i) - age * 0.003f;
      if (previous > peak) peak = previous;
    }
    for (int segment = 0; segment < SEGMENTS; ++segment) {
      const bool active = segment < static_cast<int>(level);
      const int y = BASELINE - (segment + 1) * 20;
      const float gain = active ? 0.85f : 0.055f;
      frame.fillRect(x, y, 18, 18, rgb(reds[i]*gain, greens[i]*gain, blues[i]*gain));
      if (active) {
        frame.fillRect(x, y+16, 18, 2, rgb(reds[i]/2, greens[i]/2, blues[i]/2));
      }
    }
    // Peaks snap to the same pixel grid as the square tiles.
    frame.fillRect(x, BASELINE-static_cast<int>(peak)*20-6, 18, 4,
                   rgb((reds[i]+255)/2, (greens[i]+255)/2, (blues[i]+255)/2));
    for (int tile = 0; tile < 2; ++tile) {
      frame.fillRect(x+tile*12, BASELINE+4, 6, 4,
                     rgb(reds[i]/4, greens[i]/4, blues[i]/4));
    }
  }
}

void drawWalkingCat(uint32_t elapsed) {
  frame.fillScreen(rgb(0, 0, 0));
  // Keep a few pixels visible at both ends so the loop never shows an empty screen.
  const int cycle = SCREEN_W + CAT_WALK.width - 8;
  const int travel = static_cast<int>((static_cast<uint64_t>(elapsed) * 4 / 65) % cycle);
  drawAnimationFrame(CAT_WALK, SCREEN_W - 4 - travel,
                     (SCREEN_H - CAT_WALK.height) / 2, elapsed, 1000);
}

void drawLoading(uint32_t elapsed) {
  static const int16_t positions[8][2] = {
    {150, 23}, {187, 38}, {202, 75}, {187, 112},
    {150, 127}, {113, 112}, {98, 75}, {113, 38}
  };
  static const uint8_t fade[8] = {255, 204, 153, 110, 77, 53, 35, 24};
  frame.fillScreen(rgb(3, 5, 12));

  const uint8_t head = elapsed / 100 % 8;
  for (uint8_t i = 0; i < 8; ++i) {
    const uint8_t age = (head + 8 - i) % 8;
    const uint8_t level = fade[age];
    frame.fillRect(positions[i][0], positions[i][1], 20, 20,
                   rgb(level, level, level));
  }
}

void drawMovingText(uint32_t elapsed, bool hungry) {
  const uint16_t background = hungry ? rgb(25, 5, 13) : rgb(3, 20, 24);
  frame.fillScreen(background);

  const char *word = hungry ? "HUNGRY" : "FED";
  const char *mouth = hungry ? "(" : ")";
  const int cellW = hungry ? 8 : 15;
  const int cellH = hungry ? 23 : 22;
  const int letterSpacing = hungry ? 2 : 0;
  const int wordLength = hungry ? 6 : 3;
  const int textWidth = wordLength * 5 * cellW
                      + (wordLength - 1) * (cellW + letterSpacing);
  const int textHeight = 7 * cellH;
  const int gap = 14;
  frame.setFont(&fonts::FreeSansBold24pt7b);
  frame.setTextSize(3);
  const int eyesWidth = frame.textWidth(":");
  frame.setFont(&fonts::FreeSans24pt7b);
  const int mouthWidth = frame.textWidth(mouth);
  const int emoticonWidth = eyesWidth + mouthWidth;
  const int itemWidth = textWidth + gap + emoticonWidth;
  const int repeatGap = 14;
  const int period = itemWidth + repeatGap;
  const int offset = static_cast<int>((elapsed / 10) % period);
  const int y = (SCREEN_H - textHeight) / 2;
  const uint16_t textColor = hungry ? rgb(255, 100, 83) : rgb(92, 255, 190);

  frame.setTextColor(textColor, background);
  frame.setTextWrap(false);
  frame.setTextDatum(textdatum_t::middle_left);
  for (int x = -offset; x < SCREEN_W; x += period) {
    drawBigWord(word, x, y, cellW, cellH, letterSpacing, textColor);
    const int emoticonX = x + textWidth + gap;
    frame.setFont(&fonts::FreeSansBold24pt7b);
    frame.drawString(":", emoticonX, SCREEN_H / 2);
    frame.setFont(&fonts::FreeSans24pt7b);
    frame.drawString(mouth, emoticonX + eyesWidth, SCREEN_H / 2);
  }
}

void changeScene(int direction, uint32_t now) {
  scene = (scene + SCENE_COUNT + direction) % SCENE_COUNT;
  sceneStarted = now;
}

void adjustBrightness(int direction, uint32_t now) {
  showBrightnessIndicator = true;
  brightnessChangedAt = now;
  int value = brightness + direction * BRIGHTNESS_STEP;
  if (value < BRIGHTNESS_MIN) value = BRIGHTNESS_MIN;
  if (value > BRIGHTNESS_MAX) value = BRIGHTNESS_MAX;
  if (value == brightness) return;

  brightness = value;
  display.setBrightness(brightness);
}

void drawBrightnessIndicator(uint32_t now) {
  if (!showBrightnessIndicator) return;
  if (now - brightnessChangedAt > 1200) {
    showBrightnessIndicator = false;
    return;
  }
  const int y = SCREEN_H - 4;
  frame.fillRoundRect(0, y, SCREEN_W, 4, 2, rgb(45, 45, 50));
  frame.fillRoundRect(0, y, brightness * SCREEN_W / BRIGHTNESS_MAX, 4, 2,
                      rgb(235, 235, 245));
}

void updateButton(ButtonState &button, uint32_t now) {
  switch (button.update(digitalRead(button.pin) == LOW, now)) {
    case ButtonAction::ShortPress:
      changeScene(button.direction, now);
      break;
    case ButtonAction::BrightnessStep:
      adjustBrightness(button.direction, now);
      break;
    case ButtonAction::None:
      break;
  }
}

void setup() {
  pinMode(BUTTON_NEXT, INPUT_PULLUP);
  pinMode(BUTTON_PREV, INPUT_PULLUP);

  display.begin(1, brightness); // Landscape orientation; brightness is 0..255.
  frame.setColorDepth(16);
  frame.setPsram(true);
  if (!frame.createSprite(SCREEN_W, SCREEN_H)) {
    frame.setPsram(false);
    if (!frame.createSprite(SCREEN_W, SCREEN_H)) {
      display.fillScreen(rgb(30, 0, 0));
      return;
    }
  }
  frameReady = true;
  sceneStarted = millis();
  nextButton.begin(digitalRead(BUTTON_NEXT) == LOW, sceneStarted);
  prevButton.begin(digitalRead(BUTTON_PREV) == LOW, sceneStarted);
}

void loop() {
  if (!frameReady) return;
  const uint32_t now = millis();
  updateButton(nextButton, now);
  updateButton(prevButton, now);
  if (now - lastFrame < 35) return;
  lastFrame = now;

  const uint32_t elapsed = now - sceneStarted;
  if (scene == 0) drawHearts(elapsed);
  else if (scene == 1) drawMovingText(elapsed, true);
  else if (scene == 2) drawMovingText(elapsed, false);
  else if (scene == 3) drawEqualizer(elapsed);
  else if (scene == 4) drawWalkingCat(elapsed);
  else if (scene == 5) {
    frame.fillScreen(rgb(0, 0, 0));
    drawAnimationFrame(BAD_APPLE, 0, 0, elapsed, BAD_APPLE_PERIOD_MS);
  } else drawLoading(elapsed);
  drawBrightnessIndicator(now);
  if (now - sceneStarted < PAGE_INDICATOR_MS) drawSceneDots();
  frame.pushSprite(0, 0);
}
