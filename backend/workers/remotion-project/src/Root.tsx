import React from 'react';
import { Composition } from 'remotion';
import { Main } from './Main';
import type { MainProps } from './Main';

export const fps = 30;

const defaultProps: MainProps = {
  title: 'Fliki Test',
  subtitle: 'Hello from Remotion',
  durationInSeconds: 10,
  primaryColor: '#1a73e8',
  backgroundColor: '#ffffff',
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Main"
        component={Main}
        durationInFrames={defaultProps.durationInSeconds * fps}
        fps={fps}
        width={1280}
        height={720}
        defaultProps={defaultProps as any}
        calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.round(Number(props.durationInSeconds) * fps))})}
      />
    </>
  );
};

export const Root = RemotionRoot;
