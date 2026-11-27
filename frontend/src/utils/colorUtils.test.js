import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ACCENT_PRESETS,
  DEFAULT_ACCENT_COLOR,
  calculatePopoverPosition,
  deriveAccentTokens,
  getReadableForeground,
  hexToHsv,
  hexToRgb,
  hsvToHex,
  normalizeHexColor,
  rgbToHex,
} from '../utils/colorUtils.js';

test('normalizeHexColor supports 3-digit and 6-digit hex and rejects invalid values', () => {
  assert.equal(normalizeHexColor('#635bdb'), '#635BDB');
  assert.equal(normalizeHexColor('2563eb'), '#2563EB');
  assert.equal(normalizeHexColor('#256'), '#225566');
  assert.equal(normalizeHexColor('f0a'), '#FF00AA');

  for (const invalid of ['', '#', '#12', '#12345', '#GGGGGG', 'rgb(1,2,3)', null, undefined]) {
    assert.equal(normalizeHexColor(invalid), null);
  }
});

test('color preset list includes SenderX Indigo and 12 swatches', () => {
  assert.equal(ACCENT_PRESETS.length, 12);
  assert.equal(ACCENT_PRESETS[0].color, DEFAULT_ACCENT_COLOR);
});

test('HSV / RGB / HEX conversions preserve known colors cleanly', () => {
  assert.deepEqual(hexToRgb('#FF0000'), { r: 255, g: 0, b: 0 });
  assert.equal(rgbToHex(99, 91, 219), '#635BDB');

  const hsv = hexToHsv('#2563EB');
  const roundTrip = hsvToHex(hsv.h, hsv.s, hsv.v);
  assert.equal(typeof roundTrip, 'string');
  assert.match(roundTrip, /^#[0-9A-F]{6}$/);
});

test('calculatePopoverPosition shifts left when trigger is near right viewport edge', () => {
  const pos = calculatePopoverPosition({
    triggerRect: { top: 220, bottom: 262, left: 1210, right: 1252 },
    popoverWidth: 276,
    popoverHeight: 352,
    viewportWidth: 1280,
    viewportHeight: 800,
    isRtl: false,
  });
  assert.ok(pos.left >= 12);
  assert.ok(pos.left + pos.width <= 1280 - 12);
  assert.equal(pos.openUp, false);
});

test('calculatePopoverPosition opens upward when bottom space is insufficient', () => {
  const pos = calculatePopoverPosition({
    triggerRect: { top: 690, bottom: 732, left: 950, right: 992 },
    popoverWidth: 276,
    popoverHeight: 352,
    viewportWidth: 1280,
    viewportHeight: 760,
    isRtl: false,
  });
  assert.equal(pos.openUp, true);
  assert.ok(pos.top >= 12);
  assert.ok(pos.top + 352 <= 760 - 12);
});

test('calculatePopoverPosition respects RTL and narrow mobile viewports', () => {
  const rtlPos = calculatePopoverPosition({
    triggerRect: { top: 200, bottom: 242, left: 40, right: 82 },
    popoverWidth: 276,
    popoverHeight: 352,
    viewportWidth: 360,
    viewportHeight: 720,
    isRtl: true,
  });
  assert.ok(rtlPos.left >= 12);
  assert.ok(rtlPos.left + rtlPos.width <= 360 - 12);
});

test('deriveAccentTokens generates readable contrast foreground and darker hover/active shades', () => {
  const darkAccent = deriveAccentTokens('#635BDB');
  assert.equal(darkAccent.color, '#635BDB');
  assert.equal(darkAccent.foreground, '#FFFFFF');
  assert.notEqual(darkAccent.hover, darkAccent.color);
  assert.notEqual(darkAccent.active, darkAccent.hover);

  // Bright yellow accent must automatically pick dark foreground text for legibility
  assert.equal(getReadableForeground('#FACC15'), '#0F172A');
  assert.equal(getReadableForeground('#1E293B'), '#FFFFFF');
});
