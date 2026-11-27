export const DEFAULT_ACCENT_COLOR = '#635BDB';

export const ACCENT_PRESETS = [
  { name: 'Indigo', color: '#635BDB' },
  { name: 'Purple', color: '#7C3AED' },
  { name: 'Blue', color: '#2563EB' },
  { name: 'Cyan', color: '#0891B2' },
  { name: 'Teal', color: '#0D9488' },
  { name: 'Green', color: '#16A34A' },
  { name: 'Emerald', color: '#059669' },
  { name: 'Orange', color: '#EA580C' },
  { name: 'Amber', color: '#D97706' },
  { name: 'Coral', color: '#FF6B4A' },
  { name: 'Pink', color: '#EC4899' },
  { name: 'Red', color: '#DC2626' },
];

/**
 * Normalize a 3-digit or 6-digit HEX string (with or without `#`) into `#RRGGBB`.
 * Returns `null` for invalid inputs.
 */
export function normalizeHexColor(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const raw = trimmed.startsWith('#') ? trimmed.slice(1) : trimmed;
  if (/^[0-9a-f]{3}$/i.test(raw)) {
    const expanded = raw
      .split('')
      .map((ch) => ch + ch)
      .join('');
    return `#${expanded.toUpperCase()}`;
  }
  if (/^[0-9a-f]{6}$/i.test(raw)) {
    return `#${raw.toUpperCase()}`;
  }
  return null;
}

export function clamp(val, min, max) {
  return Math.min(max, Math.max(min, val));
}

export function hexToRgb(hex) {
  const normalized = normalizeHexColor(hex);
  if (!normalized) return null;
  return {
    r: Number.parseInt(normalized.slice(1, 3), 16),
    g: Number.parseInt(normalized.slice(3, 5), 16),
    b: Number.parseInt(normalized.slice(5, 7), 16),
  };
}

export function rgbToHex(r, g, b) {
  const toHex = (n) => clamp(Math.round(n), 0, 255).toString(16).padStart(2, '0').toUpperCase();
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

export function rgbToHsv(r, g, b) {
  const rn = clamp(r, 0, 255) / 255;
  const gn = clamp(g, 0, 255) / 255;
  const bn = clamp(b, 0, 255) / 255;

  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const delta = max - min;

  let h = 0;
  if (delta !== 0) {
    if (max === rn) {
      h = 60 * (((gn - bn) / delta) % 6);
    } else if (max === gn) {
      h = 60 * ((bn - rn) / delta + 2);
    } else {
      h = 60 * ((rn - gn) / delta + 4);
    }
  }
  if (h < 0) h += 360;

  const s = max === 0 ? 0 : (delta / max) * 100;
  const v = max * 100;

  return {
    h: Math.round(h),
    s: Math.round(s),
    v: Math.round(v),
  };
}

export function hsvToRgb(h, s, v) {
  const hn = ((h % 360) + 360) % 360;
  const sn = clamp(s, 0, 100) / 100;
  const vn = clamp(v, 0, 100) / 100;

  const c = vn * sn;
  const x = c * (1 - Math.abs(((hn / 60) % 2) - 1));
  const m = vn - c;

  let rp = 0;
  let gp = 0;
  let bp = 0;

  if (hn < 60) {
    [rp, gp, bp] = [c, x, 0];
  } else if (hn < 120) {
    [rp, gp, bp] = [x, c, 0];
  } else if (hn < 180) {
    [rp, gp, bp] = [0, c, x];
  } else if (hn < 240) {
    [rp, gp, bp] = [0, x, c];
  } else if (hn < 300) {
    [rp, gp, bp] = [x, 0, c];
  } else {
    [rp, gp, bp] = [c, 0, x];
  }

  return {
    r: Math.round((rp + m) * 255),
    g: Math.round((gp + m) * 255),
    b: Math.round((bp + m) * 255),
  };
}

export function hexToHsv(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return { h: 244, s: 58, v: 86 };
  return rgbToHsv(rgb.r, rgb.g, rgb.b);
}

export function hsvToHex(h, s, v) {
  const { r, g, b } = hsvToRgb(h, s, v);
  return rgbToHex(r, g, b);
}

export function isLightColor(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  return luminance > 0.68;
}

function relativeLuminance(rgb) {
  const channel = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b);
}

/**
 * Select `#FFFFFF` or `#0F172A` foreground depending on WCAG contrast ratio against `hex`.
 */
export function getReadableForeground(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return '#FFFFFF';
  const bgLum = relativeLuminance(rgb);
  const contrastWhite = 1.05 / (bgLum + 0.05);
  const contrastDark = (bgLum + 0.05) / 0.068;
  return contrastDark > contrastWhite + 0.35 ? '#0F172A' : '#FFFFFF';
}

export function mixHexColors(hexA, hexB, weightA = 0.88) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return normalizeHexColor(hexA) || DEFAULT_ACCENT_COLOR;
  const wA = clamp(weightA, 0, 1);
  const wB = 1 - wA;
  return rgbToHex(
    a.r * wA + b.r * wB,
    a.g * wA + b.g * wB,
    a.b * wA + b.b * wB
  );
}

/**
 * Derive dynamic button & surface tokens from any valid accent color.
 */
export function deriveAccentTokens(accentHex) {
  const color = normalizeHexColor(accentHex) || DEFAULT_ACCENT_COLOR;
  const rgb = hexToRgb(color) || { r: 99, g: 91, b: 219 };
  const hover = mixHexColors(color, '#000000', 0.88);
  const active = mixHexColors(color, '#000000', 0.78);
  const foreground = getReadableForeground(color);
  const rgbStr = `${rgb.r}, ${rgb.g}, ${rgb.b}`;

  return {
    color,
    hover,
    active,
    foreground,
    rgb: rgbStr,
    focusRing: `rgba(${rgbStr}, 0.28)`,
    subtle: `rgba(${rgbStr}, 0.14)`,
    border: `rgba(${rgbStr}, 0.34)`,
    shadow: `rgba(${rgbStr}, 0.26)`,
    shadowHover: `rgba(${rgbStr}, 0.36)`,
  };
}

/**
 * Compute viewport-clamped floating popover coordinates relative to a trigger rect,
 * accounting for RTL/LTR direction and flipping above/left when space is constrained.
 */
export function calculatePopoverPosition({
  triggerRect,
  popoverWidth = 276,
  popoverHeight = 352,
  viewportWidth,
  viewportHeight,
  isRtl = false,
  margin = 12,
  gap = 8,
}) {
  const maxWidth = Math.max(200, viewportWidth - margin * 2);
  const width = Math.min(popoverWidth, maxWidth);
  const height = Math.min(popoverHeight, Math.max(180, viewportHeight - margin * 2));

  // Horizontal placement: align toward panel interior and stay inside viewport bounds.
  let left;
  if (isRtl) {
    const alignRightEdge = triggerRect.right - width;
    const alignLeftEdge = triggerRect.left;
    const fitsRightToLeft = alignRightEdge >= margin;
    const fitsLeftToRight = alignLeftEdge + width <= viewportWidth - margin;
    if (fitsRightToLeft) {
      left = alignRightEdge;
    } else if (fitsLeftToRight) {
      left = alignLeftEdge;
    } else {
      left = viewportWidth - width - margin;
    }
  } else {
    const fitsLeftAlignedRightward = triggerRect.left + width <= viewportWidth - margin;
    const alignRightEdgeLeftward = triggerRect.right - width;
    if (fitsLeftAlignedRightward) {
      left = triggerRect.left;
    } else if (alignRightEdgeLeftward >= margin) {
      left = alignRightEdgeLeftward;
    } else {
      left = viewportWidth - width - margin;
    }
  }
  left = clamp(Math.round(left), margin, Math.max(margin, viewportWidth - width - margin));

  // Vertical placement: prefer below trigger, flip above when below space is insufficient.
  const spaceBelow = viewportHeight - triggerRect.bottom - margin;
  const spaceAbove = triggerRect.top - margin;
  const openUp = spaceBelow < height + gap && spaceAbove > spaceBelow;

  let top = openUp
    ? triggerRect.top - height - gap
    : triggerRect.bottom + gap;
  top = clamp(Math.round(top), margin, Math.max(margin, viewportHeight - height - margin));

  return {
    top,
    left,
    width,
    openUp,
  };
}
