import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import type { TemplatePlanPayload } from './Main';

const _animationProgress = (frame: number, fps: number, delay: number | null | undefined, duration: number): number => {
  const start = Math.max(0, Math.round((delay || 0) * fps));
  if (frame <= start) return 0;
  const span = Math.max(1, duration - start);
  return Math.max(0, Math.min(1, (frame - start) / span));
};

const _baseStyle = (
  canvas: { width: number; height: number },
  pos?: string | null,
  x?: number | null,
  y?: number | null,
): React.CSSProperties => {
  const style: React.CSSProperties = { position: 'absolute', color: '#fff', fontFamily: 'sans-serif', textAlign: 'center' };
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  switch (pos) {
    case 'top-left': style.left = 40; style.top = 40; break;
    case 'top-right': style.right = 40; style.top = 40; break;
    case 'top-center': style.left = cx; style.top = 40; style.transform = 'translateX(-50%)'; break;
    case 'bottom-left': style.left = 40; style.bottom = 40; break;
    case 'bottom-right': style.right = 40; style.bottom = 40; break;
    case 'center':
    default:
      style.left = cx + (x || 0);
      style.top = cy + (y || 0);
      style.transform = 'translate(-50%, -50%)';
  }
  return style;
};

export const TemplateOverlay: React.FC<{ plan: TemplatePlanPayload }> = ({ plan }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  if (!plan || !Array.isArray(plan.layers) || plan.layers.length === 0) return null;
  const canvas = { width: 1280, height: 720 };
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {plan.layers.map((layer, idx) => {
        if (!layer) return null;
        const p = _animationProgress(frame, fps, layer.delay || 0, durationInFrames);
        const opacity = layer.animation === 'fade_in' || layer.animation === 'fade_up' || layer.animation === 'scale_in' ? p : 1;
        const translateY = layer.animation === 'fade_up' || layer.animation === 'slide_up' ? (1 - p) * 24 : 0;
        const scale = layer.animation === 'scale_in' ? 0.85 + 0.15 * p : 1;
        const color = layer.color || '#ffffff';
        const fontSize = layer.font_size || 36;
        const text = layer.text == null ? '' : String(layer.text);
        const base = _baseStyle(canvas, layer.position || 'center', layer.x, layer.y);
        const baseTransform = (base.transform as string) || '';
        const key = 'tp-' + (layer.type || 'layer') + '-' + idx;
        if (layer.type === 'divider') {
          return (
            <div key={key} style={{
              position: 'absolute', left: '50%', top: 'calc(50% + ' + (layer.y || 0) + 'px)',
              width: layer.width || 60, height: layer.height || 3, background: color,
              transform: 'translate(-50%, -50%)', opacity,
            }} />
          );
        }
        if (layer.type === 'cta_button') {
          return (
            <div key={key} style={{
              ...base, background: layer.bg_color || '#48d58b', color,
              padding: (layer.padding || 20) + 'px ' + ((layer.padding || 20) * 1.6) + 'px',
              borderRadius: 12, fontSize, fontWeight: 800, opacity,
              transform: baseTransform + ' scale(' + scale + ')',
            }}>{text}</div>
          );
        }
        if (layer.type === 'step_card') {
          return (
            <div key={key} style={{
              ...base, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.18)',
              borderRadius: 16, padding: 24, minWidth: 220, color, opacity, transform: baseTransform,
            }}>
              <div style={{ fontSize: 28, fontWeight: 600, color: '#8ba7ff', marginBottom: 8 }}>Step {layer.index || 0}</div>
              <div style={{ fontSize, fontWeight: 700, lineHeight: 1.3 }}>{text}</div>
            </div>
          );
        }
        if (layer.type === 'big_number') {
          return (
            <div key={key} style={{
              ...base, fontSize: Math.max(96, fontSize), fontWeight: layer.font_weight || 800, color, opacity,
              transform: baseTransform + ' scale(' + scale + ')',
            }}>{text}</div>
          );
        }
        if (layer.type === 'big_quote') {
          return (
            <div key={key} style={{
              ...base, fontSize: Math.max(120, fontSize), fontWeight: 700, color, opacity, lineHeight: 1,
            }}>{text}</div>
          );
        }
        return (
          <div key={key} style={{
            ...base, fontSize, color,
            fontWeight: layer.font_weight || (layer.type === 'logo_text' || layer.type === 'unit' ? 600 : 700),
            maxWidth: layer.max_width || 1100, lineHeight: layer.line_height || 1.3,
            transform: baseTransform + ' translateY(' + translateY + 'px) scale(' + scale + ')',
            opacity,
          }}>{(layer.prefix || '') + text}</div>
        );
      })}
    </AbsoluteFill>
  );
};
