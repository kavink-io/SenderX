import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ACCENT_PRESETS,
  DEFAULT_ACCENT_COLOR,
  calculatePopoverPosition,
  clamp,
  hexToHsv,
  hexToRgb,
  hsvToHex,
  isLightColor,
  normalizeHexColor,
  rgbToHex,
} from '../../utils/colorUtils';

export default function AccentColorPicker({
  value = DEFAULT_ACCENT_COLOR,
  defaultColor = DEFAULT_ACCENT_COLOR,
  direction = 'ltr',
  onChange,
  onPreviewChange,
  onPreviewClear,
}) {
  const normalizedValue = normalizeHexColor(value) || defaultColor;
  const [hexInput, setHexInput] = useState(normalizedValue);
  const [hexError, setHexError] = useState(false);

  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [hsv, setHsv] = useState(() => hexToHsv(normalizedValue));
  const [popoverHexInput, setPopoverHexInput] = useState(normalizedValue);
  const [popoverHexError, setPopoverHexError] = useState(false);
  const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0, width: 276, openUp: false });

  const swatchRefs = useRef([]);
  const triggerRef = useRef(null);
  const popoverRef = useRef(null);
  const svAreaRef = useRef(null);
  const hueBarRef = useRef(null);
  const draggingTargetRef = useRef(null); // 'sv' | 'hue' | null
  const latestHsvRef = useRef(hsv);
  latestHsvRef.current = hsv;

  const baseId = useId();
  const errorId = `${baseId}-hex-error`;
  const popoverErrorId = `${baseId}-popover-hex-error`;
  const popoverTitleId = `${baseId}-popover-title`;

  useEffect(() => {
    setHexInput(normalizedValue);
    setHexError(false);
    if (!isPopoverOpen) {
      setHsv(hexToHsv(normalizedValue));
      setPopoverHexInput(normalizedValue);
      setPopoverHexError(false);
    }
  }, [normalizedValue, isPopoverOpen]);

  const draftHex = hsvToHex(hsv.h, hsv.s, hsv.v);
  const draftRgb = hexToRgb(draftHex) || { r: 99, g: 91, b: 219 };

  const commitColor = useCallback((nextColor) => {
    const valid = normalizeHexColor(nextColor);
    if (!valid) return false;
    setHexInput(valid);
    setHexError(false);
    setPopoverHexInput(valid);
    setPopoverHexError(false);
    setHsv(hexToHsv(valid));
    onPreviewClear?.();
    onChange?.(valid);
    return true;
  }, [onChange, onPreviewClear]);

  const updatePopoverPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const triggerRect = triggerRef.current.getBoundingClientRect();
    const measuredRect = popoverRef.current?.getBoundingClientRect();
    const popoverWidth = measuredRect?.width || 276;
    const popoverHeight = measuredRect?.height || 360;
    const isRtl = direction === 'rtl' || document.documentElement.getAttribute('dir') === 'rtl';

    setPopoverPos(
      calculatePopoverPosition({
        triggerRect,
        popoverWidth,
        popoverHeight,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        isRtl,
      })
    );
  }, [direction]);

  useLayoutEffect(() => {
    if (!isPopoverOpen) return;
    updatePopoverPosition();
    const raf = window.requestAnimationFrame(updatePopoverPosition);
    return () => window.cancelAnimationFrame(raf);
  }, [isPopoverOpen, updatePopoverPosition]);

  useEffect(() => {
    if (!isPopoverOpen) return undefined;

    const handleOutside = (event) => {
      if (
        triggerRef.current?.contains(event.target) ||
        popoverRef.current?.contains(event.target)
      ) {
        return;
      }
      onPreviewClear?.();
      setIsPopoverOpen(false);
    };

    const handleEscapeCapture = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === 'function') {
          event.stopImmediatePropagation();
        }
        onPreviewClear?.();
        setIsPopoverOpen(false);
        triggerRef.current?.focus();
      }
    };

    const handleReposition = (event) => {
      if (popoverRef.current && event?.target instanceof Node && popoverRef.current.contains(event.target)) {
        return;
      }
      updatePopoverPosition();
    };

    document.addEventListener('mousedown', handleOutside, true);
    document.addEventListener('touchstart', handleOutside, true);
    document.addEventListener('keydown', handleEscapeCapture, true);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);

    return () => {
      document.removeEventListener('mousedown', handleOutside, true);
      document.removeEventListener('touchstart', handleOutside, true);
      document.removeEventListener('keydown', handleEscapeCapture, true);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isPopoverOpen, onPreviewClear, updatePopoverPosition]);

  const applyDraftHsv = useCallback((nextHsv, shouldCommit = false) => {
    const clampedHsv = {
      h: clamp(Math.round(nextHsv.h), 0, 360),
      s: clamp(Math.round(nextHsv.s), 0, 100),
      v: clamp(Math.round(nextHsv.v), 0, 100),
    };
    setHsv(clampedHsv);
    latestHsvRef.current = clampedHsv;
    const nextColor = hsvToHex(clampedHsv.h, clampedHsv.s, clampedHsv.v);
    setPopoverHexInput(nextColor);
    setPopoverHexError(false);
    setHexInput(nextColor);
    setHexError(false);

    if (shouldCommit) {
      onPreviewClear?.();
      onChange?.(nextColor);
    } else {
      onPreviewChange?.(nextColor);
    }
  }, [onChange, onPreviewChange, onPreviewClear]);

  const updateSvFromCoordinates = useCallback((clientX, clientY, commit = false) => {
    const area = svAreaRef.current;
    if (!area) return;
    const rect = area.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratioX = clamp((clientX - rect.left) / rect.width, 0, 1);
    const ratioY = clamp((clientY - rect.top) / rect.height, 0, 1);
    applyDraftHsv(
      {
        h: latestHsvRef.current.h,
        s: Math.round(ratioX * 100),
        v: Math.round((1 - ratioY) * 100),
      },
      commit
    );
  }, [applyDraftHsv]);

  const updateHueFromCoordinates = useCallback((clientX, commit = false) => {
    const bar = hueBarRef.current;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    if (!rect.width) return;
    const ratioX = clamp((clientX - rect.left) / rect.width, 0, 1);
    applyDraftHsv(
      {
        ...latestHsvRef.current,
        h: Math.round(ratioX * 360),
      },
      commit
    );
  }, [applyDraftHsv]);

  useEffect(() => {
    if (!isPopoverOpen) return undefined;

    const handlePointerMove = (event) => {
      if (!draggingTargetRef.current) return;
      if (draggingTargetRef.current === 'sv') {
        updateSvFromCoordinates(event.clientX, event.clientY, false);
      } else if (draggingTargetRef.current === 'hue') {
        updateHueFromCoordinates(event.clientX, false);
      }
    };

    const handlePointerEnd = () => {
      if (!draggingTargetRef.current) return;
      draggingTargetRef.current = null;
      const finalHex = hsvToHex(latestHsvRef.current.h, latestHsvRef.current.s, latestHsvRef.current.v);
      onPreviewClear?.();
      onChange?.(finalHex);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerEnd);
    window.addEventListener('pointercancel', handlePointerEnd);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerEnd);
      window.removeEventListener('pointercancel', handlePointerEnd);
    };
  }, [isPopoverOpen, onChange, onPreviewClear, updateHueFromCoordinates, updateSvFromCoordinates]);

  const handleMainHexChange = (raw) => {
    setHexInput(raw);
    const normalized = normalizeHexColor(raw);
    if (normalized) {
      setHexError(false);
      setHsv(hexToHsv(normalized));
      setPopoverHexInput(normalized);
      setPopoverHexError(false);
      onChange?.(normalized);
    } else if (raw.trim().length >= 7) {
      setHexError(true);
    }
  };

  const handleMainHexBlur = () => {
    const normalized = normalizeHexColor(hexInput);
    if (normalized) {
      commitColor(normalized);
    } else {
      setHexError(true);
    }
  };

  const handleSwatchKeyDown = (index, event) => {
    const cols = 6;
    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % ACCENT_PRESETS.length;
    else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + ACCENT_PRESETS.length) % ACCENT_PRESETS.length;
    else if (event.key === 'ArrowDown') nextIndex = Math.min(ACCENT_PRESETS.length - 1, index + cols);
    else if (event.key === 'ArrowUp') nextIndex = Math.max(0, index - cols);

    if (nextIndex !== null) {
      event.preventDefault();
      swatchRefs.current[nextIndex]?.focus();
    }
  };

  const handlePopoverHexChange = (raw) => {
    setPopoverHexInput(raw);
    const normalized = normalizeHexColor(raw);
    if (normalized) {
      setPopoverHexError(false);
      const nextHsv = hexToHsv(normalized);
      setHsv(nextHsv);
      latestHsvRef.current = nextHsv;
      setHexInput(normalized);
      setHexError(false);
      onPreviewChange?.(normalized);
    } else {
      setPopoverHexError(true);
    }
  };

  const handleRgbChannelChange = (channel, raw) => {
    if (raw === '') return;
    const numeric = Number.parseInt(raw, 10);
    if (Number.isNaN(numeric)) return;
    const nextRgb = { ...draftRgb, [channel]: clamp(numeric, 0, 255) };
    const nextColor = rgbToHex(nextRgb.r, nextRgb.g, nextRgb.b);
    applyDraftHsv(hexToHsv(nextColor), true);
  };

  const togglePopover = () => {
    if (isPopoverOpen) {
      onPreviewClear?.();
      setIsPopoverOpen(false);
    } else {
      setHsv(hexToHsv(normalizedValue));
      setPopoverHexInput(normalizedValue);
      setPopoverHexError(false);
      setIsPopoverOpen(true);
    }
  };

  const pureHueHex = hsvToHex(hsv.h, 100, 100);
  const thumbLeft = `${hsv.s}%`;
  const thumbTop = `${100 - hsv.v}%`;

  return (
    <div className="accent-color-picker">
      <div className="palette-grid" role="group" aria-label="Preset accent colors">
        {ACCENT_PRESETS.map((preset, index) => {
          const selected = normalizedValue.toLowerCase() === preset.color.toLowerCase();
          const checkColor = isLightColor(preset.color) ? '#0F172A' : '#FFFFFF';
          return (
            <button
              ref={(el) => { swatchRefs.current[index] = el; }}
              type="button"
              key={preset.name}
              className={`palette-swatch${selected ? ' is-selected' : ''}`}
              title={`${preset.name} (${preset.color})`}
              aria-label={`${preset.name}${selected ? ', selected' : ''}`}
              aria-pressed={selected}
              onClick={() => commitColor(preset.color)}
              onKeyDown={(event) => handleSwatchKeyDown(index, event)}
              style={{ '--swatch-color': preset.color, '--swatch-check-color': checkColor }}
            >
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="m3.5 8.2 2.8 2.7 6.2-6.1" />
              </svg>
            </button>
          );
        })}
      </div>

      <div className="hex-control">
        <input
          className="form-control"
          type="text"
          value={hexInput}
          maxLength={7}
          placeholder="#635BDB"
          spellCheck="false"
          aria-label="Custom HEX color"
          aria-invalid={hexError}
          aria-describedby={hexError ? errorId : undefined}
          onChange={(e) => handleMainHexChange(e.target.value)}
          onBlur={handleMainHexBlur}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleMainHexBlur();
            }
          }}
        />
        <button
          ref={triggerRef}
          type="button"
          className={`accent-color-preview-btn${isPopoverOpen ? ' is-open' : ''}`}
          aria-label="Open custom accent color picker"
          aria-haspopup="dialog"
          aria-expanded={isPopoverOpen}
          title="Choose custom color"
          onClick={togglePopover}
        >
          <span
            className="color-preview"
            style={{ background: isPopoverOpen ? draftHex : normalizedValue }}
          />
        </button>
      </div>

      {hexError && (
        <p className="accent-color-error" id={errorId} role="alert">
          Enter a valid 3-digit or 6-digit HEX color (e.g. #2563EB or #256).
        </p>
      )}

      {isPopoverOpen && createPortal(
        <div
          ref={popoverRef}
          role="dialog"
          aria-modal="false"
          aria-labelledby={popoverTitleId}
          dir={direction}
          className={`accent-popover${popoverPos.openUp ? ' is-up' : ''}`}
          style={{
            position: 'fixed',
            top: `${popoverPos.top}px`,
            left: `${popoverPos.left}px`,
            width: `${popoverPos.width}px`,
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="accent-popover-header">
            <span id={popoverTitleId} className="accent-popover-title">Custom Accent Color</span>
            <span className="accent-popover-chip" style={{ background: draftHex }} aria-hidden="true" />
          </div>

          <div
            ref={svAreaRef}
            role="slider"
            dir="ltr"
            tabIndex={0}
            aria-label="Color saturation and brightness"
            aria-valuetext={`Saturation ${hsv.s}%, Brightness ${hsv.v}%`}
            className="accent-sv-area"
            style={{ backgroundColor: pureHueHex }}
            onPointerDown={(event) => {
              event.preventDefault();
              draggingTargetRef.current = 'sv';
              updateSvFromCoordinates(event.clientX, event.clientY, false);
            }}
            onKeyDown={(event) => {
              const step = event.shiftKey ? 10 : 3;
              if (event.key === 'ArrowRight') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, s: hsv.s + step }, true);
              } else if (event.key === 'ArrowLeft') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, s: hsv.s - step }, true);
              } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, v: hsv.v + step }, true);
              } else if (event.key === 'ArrowDown') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, v: hsv.v - step }, true);
              }
            }}
          >
            <div className="accent-sv-white" />
            <div className="accent-sv-black" />
            <span
              className="accent-sv-thumb"
              style={{ left: thumbLeft, top: thumbTop, background: draftHex }}
            />
          </div>

          <div
            ref={hueBarRef}
            role="slider"
            dir="ltr"
            tabIndex={0}
            aria-label="Hue"
            aria-valuemin={0}
            aria-valuemax={360}
            aria-valuenow={hsv.h}
            className="accent-hue-slider"
            onPointerDown={(event) => {
              event.preventDefault();
              draggingTargetRef.current = 'hue';
              updateHueFromCoordinates(event.clientX, false);
            }}
            onKeyDown={(event) => {
              const step = event.shiftKey ? 15 : 5;
              if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, h: (hsv.h + step) % 360 }, true);
              } else if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
                event.preventDefault();
                applyDraftHsv({ ...hsv, h: (hsv.h - step + 360) % 360 }, true);
              }
            }}
          >
            <span
              className="accent-hue-thumb"
              style={{ left: `${(hsv.h / 360) * 100}%`, background: pureHueHex }}
            />
          </div>

          <div className="accent-popover-inputs" dir="ltr">
            <label className="accent-field">
              <span>HEX</span>
              <input
                type="text"
                className="form-control"
                value={popoverHexInput}
                maxLength={7}
                spellCheck="false"
                aria-label="Popover HEX input"
                aria-invalid={popoverHexError}
                aria-describedby={popoverHexError ? popoverErrorId : undefined}
                onChange={(e) => handlePopoverHexChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    if (commitColor(popoverHexInput)) {
                      setIsPopoverOpen(false);
                    }
                  }
                }}
              />
            </label>

            <div className="accent-rgb-row" aria-label="RGB color channels">
              {(['r', 'g', 'b']).map((channel) => (
                <label className="accent-field" key={channel}>
                  <span>{channel.toUpperCase()}</span>
                  <input
                    type="number"
                    className="form-control"
                    min={0}
                    max={255}
                    value={draftRgb[channel]}
                    aria-label={`${channel.toUpperCase()} channel`}
                    onChange={(e) => handleRgbChannelChange(channel, e.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>

          {popoverHexError && (
            <p className="accent-color-error" id={popoverErrorId} role="alert">
              Use 3 or 6 hex characters.
            </p>
          )}

          <div className="accent-popover-footer">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => commitColor(defaultColor)}
            >
              Reset
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                const candidate = normalizeHexColor(popoverHexInput) || draftHex;
                if (commitColor(candidate)) {
                  setIsPopoverOpen(false);
                  triggerRef.current?.focus();
                }
              }}
            >
              Apply
            </button>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
