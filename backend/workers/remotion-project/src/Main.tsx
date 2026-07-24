import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type AvatarPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'top-center'
  | 'bottom-center'
  | 'center';

export type AvatarShape = 'circle' | 'rounded' | 'square';

export type AspectRatio = '16:9' | '9:16' | '1:1';

export interface AvatarLayout {
  position?: AvatarPosition;
  widthPx?: number;
  heightPx?: number;
  marginPx?: number;
  borderColor?: string;
  borderPx?: number;
  borderRadiusPx?: number;
  shapeBorderRadii?: {
    circle?: number;
    rounded?: number;
    square?: number;
  };
  shape?: AvatarShape;
  showLabel?: boolean;
}

export interface SceneProps {
  id: string;
  title: string;
  subtitle: string;
  durationInSeconds: number;
  videoSrc?: string;
  imageSrc?: string;
  audioSrc?: string;
  avatarSrc?: string;
  avatarFallback?: boolean;
  avatarMode?: string;
  avatarName?: string;
  avatarUuid?: string;
  avatarLayout?: AvatarLayout;
}

export interface MainProps {
  title: string;
  subtitle: string;
  durationInSeconds: number;
  primaryColor: string;
  backgroundColor: string;
  scenes?: SceneProps[];
  musicSrc?: string;
  musicVolume?: number;
  aspectRatio?: AspectRatio;
  avatarLayout?: AvatarLayout;
}

const DEFAULT_AVATAR_LAYOUT: Required<Omit<AvatarLayout, 'position' | 'shape'>> & {
  position: AvatarPosition;
  shape: AvatarShape;
} = {
  position: 'bottom-right',
  widthPx: 320,
  heightPx: 240,
  marginPx: 80,
  borderColor: 'rgba(255,255,255,0.92)',
  borderPx: 3,
  borderRadiusPx: 16,
  shape: 'rounded',
  showLabel: true,
};

const ASPECT_DIMENSIONS: Record<AspectRatio, { width: number; height: number }> = {
  '16:9': { width: 1280, height: 720 },
  '9:16': { width: 720, height: 1280 },
  '1:1': { width: 720, height: 720 },
};

function _shapeRadius(merged: AvatarLayout, base: Required<AvatarLayout>): number {
  const shapeRadii = merged.shapeBorderRadii ?? {};
  const shape = merged.shape ?? DEFAULT_AVATAR_LAYOUT.shape;
  if (typeof shapeRadii[shape] === 'number') return shapeRadii[shape];
  if (shape === 'circle') return Math.max(base.widthPx, base.heightPx) / 2;
  if (shape === 'square') return 0;
  return base.borderRadiusPx;
}

function resolveLayout(sceneLayout: AvatarLayout | undefined, globalLayout: AvatarLayout | undefined): Required<AvatarLayout> {
  const merged: AvatarLayout = { ...(globalLayout ?? {}), ...(sceneLayout ?? {}) };
  const base: Required<AvatarLayout> = {
    position: merged.position ?? DEFAULT_AVATAR_LAYOUT.position,
    widthPx: merged.widthPx ?? DEFAULT_AVATAR_LAYOUT.widthPx,
    heightPx: merged.heightPx ?? DEFAULT_AVATAR_LAYOUT.heightPx,
    marginPx: merged.marginPx ?? DEFAULT_AVATAR_LAYOUT.marginPx,
    borderColor: merged.borderColor ?? DEFAULT_AVATAR_LAYOUT.borderColor,
    borderPx: merged.borderPx ?? DEFAULT_AVATAR_LAYOUT.borderPx,
    borderRadiusPx: merged.borderRadiusPx ?? DEFAULT_AVATAR_LAYOUT.borderRadiusPx,
    shape: merged.shape ?? DEFAULT_AVATAR_LAYOUT.shape,
    showLabel: merged.showLabel ?? DEFAULT_AVATAR_LAYOUT.showLabel,
  };
  base.borderRadiusPx = _shapeRadius(merged, base);
  return base;
}

function avatarBoxStyle(
  layout: Required<AvatarLayout>,
  canvas: { width: number; height: number },
): React.CSSProperties {
  // borderRadiusPx 已在 resolveLayout 中按 shapeBorderRadii / shape 默认值算好, 直接用.
  const { widthPx, heightPx, marginPx, position, borderColor, borderPx, borderRadiusPx } = layout;
  const style: React.CSSProperties = {
    position: 'absolute',
    width: widthPx,
    height: heightPx,
    overflow: 'hidden',
    border:
      borderColor && borderPx
        ? `${borderPx}px solid ${borderColor}`
        : undefined,
    boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
    backgroundColor: '#000',
  };
  // borderRadiusPx 已在 resolveLayout 中按 shapeBorderRadii / shape 默认值算好, 直接用.
  style.borderRadius = borderRadiusPx;
  const verticalCenter = (canvas.height - heightPx) / 2;
  const horizontalCenter = (canvas.width - widthPx) / 2;
  switch (position) {
    case 'top-left':
      style.top = marginPx;
      style.left = marginPx;
      break;
    case 'top-right':
      style.top = marginPx;
      style.right = marginPx;
      break;
    case 'bottom-left':
      style.bottom = marginPx;
      style.left = marginPx;
      break;
    case 'bottom-center':
      style.bottom = marginPx;
      style.left = horizontalCenter;
      break;
    case 'top-center':
      style.top = marginPx;
      style.left = horizontalCenter;
      break;
    case 'center':
      style.top = verticalCenter;
      style.left = horizontalCenter;
      break;
    case 'bottom-right':
    default:
      style.bottom = marginPx;
      style.right = marginPx;
      break;
  }
  return style;
}

function subtitleReserve(layout: Required<AvatarLayout>, canvas: { width: number; height: number }): {
  left: number;
  right: number;
} {
  const blockingPositions: AvatarPosition[] = [
    'bottom-left', 'bottom-right', 'top-left', 'top-right', 'bottom-center', 'top-center',
  ];
  if (!blockingPositions.includes(layout.position)) {
    return { left: 80, right: 80 };
  }
  const reserved = layout.widthPx + layout.marginPx * 2;
  if (layout.position.endsWith('-left')) {
    return { left: 80, right: Math.max(80, reserved) };
  }
  if (layout.position.endsWith('-right')) {
    return { left: Math.max(80, reserved), right: 80 };
  }
  return { left: Math.max(80, reserved / 2), right: Math.max(80, reserved / 2) };
}

const Scene: React.FC<{
  scene: SceneProps;
  primaryColor: string;
  backgroundColor: string;
  layout: Required<AvatarLayout>;
  canvas: { width: number; height: number };
}> = ({ scene, primaryColor, backgroundColor, layout, canvas }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(
    frame,
    [0, Math.min(12, fps / 2)],
    [0, 1],
    { extrapolateRight: 'clamp' },
  );

  const hasAvatar = Boolean(scene.avatarSrc);
  const avatarLabel = scene.avatarFallback
    ? `${scene.avatarName || 'Avatar'}·静态头像`
    : scene.avatarName || 'Avatar';

  const boxStyle = hasAvatar ? avatarBoxStyle(layout, canvas) : undefined;
  const labelBottomOffset = layout.position.startsWith('top')
    ? layout.marginPx + layout.heightPx + 12
    : layout.marginPx + layout.heightPx + 12;

  const subtitlePadding = subtitleReserve(layout, canvas);

  return (
    <AbsoluteFill style={{ backgroundColor, overflow: 'hidden' }}>
      {scene.videoSrc ? (
        <OffthreadVideo
          src={scene.videoSrc}
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : scene.imageSrc ? (
        <Img
          src={scene.imageSrc}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : null}

      {hasAvatar && boxStyle ? (
        <>
          <div style={boxStyle} aria-label="avatar-clip">
            <OffthreadVideo
              src={scene.avatarSrc}
              muted={false}
              volume={0}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
          </div>
          {layout.showLabel && (
            <div
              style={{
                position: 'absolute',
                right:
                  layout.position.endsWith('-left') ? 'auto' : layout.marginPx,
                left:
                  layout.position.endsWith('-left') ? layout.marginPx : 'auto',
                top: layout.position.startsWith('top') ? labelBottomOffset : 'auto',
                bottom: layout.position.startsWith('top') ? 'auto' : labelBottomOffset,
                maxWidth: layout.widthPx,
                padding: '6px 12px',
                borderRadius: 999,
                background: scene.avatarFallback
                  ? 'rgba(220,80,80,0.85)'
                  : 'rgba(0,0,0,0.55)',
                color: '#fff',
                fontFamily: 'sans-serif',
                fontWeight: 600,
                fontSize: 20,
                letterSpacing: 0.3,
                textShadow: '0 2px 6px rgba(0,0,0,0.45)',
                opacity,
              }}
              title={
                scene.avatarFallback
                  ? 'Avatar 缺失模型/依赖, 已回退静态头像 MP4'
                  : 'Wav2Lip-ONNX 数字人'
              }
            >
              {avatarLabel}
            </div>
          )}
        </>
      ) : null}

      <AbsoluteFill style={{ background: 'linear-gradient(180deg,rgba(0,0,0,.08),rgba(0,0,0,.62))' }} />
      <div
        style={{
          position: 'absolute',
          left: subtitlePadding.left,
          right: subtitlePadding.right,
          bottom: 72,
          color: primaryColor,
          opacity,
          textShadow: '0 3px 18px rgba(0,0,0,0.65)',
        }}
      >
        <div style={{ fontFamily: 'sans-serif', fontWeight: 800, fontSize: 52, marginBottom: 18 }}>
          {scene.title}
        </div>
        <div style={{ fontFamily: 'sans-serif', fontWeight: 600, fontSize: 36, lineHeight: 1.35 }}>
          {scene.subtitle}
        </div>
      </div>
      {scene.audioSrc ? <Audio src={scene.audioSrc} /> : null}
    </AbsoluteFill>
  );
};

export const Main: React.FC<MainProps> = ({
  title,
  subtitle,
  primaryColor,
  backgroundColor,
  scenes = [],
  musicSrc,
  musicVolume = 0.12,
  aspectRatio = '16:9',
  avatarLayout,
}) => {
  const canvas = ASPECT_DIMENSIONS[aspectRatio] ?? ASPECT_DIMENSIONS['16:9'];
  const globalLayout = resolveLayout(undefined, avatarLayout);

  if (!scenes.length) {
    return (
      <AbsoluteFill
        style={{
          backgroundColor,
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <h1 style={{ fontSize: 96, color: primaryColor, fontFamily: 'sans-serif' }}>
          {title}
        </h1>
        <p style={{ fontSize: 48, color: '#aaa', fontFamily: 'sans-serif' }}>{subtitle}</p>
      </AbsoluteFill>
    );
  }
  let start = 0;
  return (
    <AbsoluteFill style={{ backgroundColor, width: canvas.width, height: canvas.height }}>
      {scenes.map((scene) => {
        const duration = Math.max(1, Math.round(scene.durationInSeconds * 30));
        const from = start;
        start += duration;
        const layout = resolveLayout(scene.avatarLayout, avatarLayout);
        return (
          <Sequence
            key={scene.id}
            from={from}
            durationInFrames={duration}
          >
            <Scene
              scene={scene}
              primaryColor={primaryColor}
              backgroundColor={backgroundColor}
              layout={layout}
              canvas={canvas}
            />
          </Sequence>
        );
      })}
      {musicSrc ? <Audio src={musicSrc} volume={musicVolume} loop /> : null}
    </AbsoluteFill>
  );
};
