import React from "react";
import { Composition } from "remotion";
import { ForkyReel, calcDurationInFrames } from "./ForkyReel";
import type { ReelProps } from "./types";

// Safe defaults so the composition opens in Studio even with no inputProps.
const defaultProps: ReelProps = {
  brand: {
    name: "La Medusa",
    handle: "lamedusarestaurant.ca",
    primaryColor: "#d6b646",
    bgColor: "#1d1c1a",
    textColor: "#f5f0e8",
    titleFont: "PlayfairDisplay",
    bodyFont: "Montserrat",
  },
  scenes: [
    { src: "placeholder.png", kind: "image", durationInSeconds: 4, text: "Sample caption" },
  ],
  intro: { title: "La Medusa", subtitle: "Depuis 1996" },
  outro: { title: "La Medusa", cta: "Réservation en bio 🔗" },
  voiceover: null,
  music: null,
  fps: 30,
  width: 1080,
  height: 1920,
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ForkyReel"
      component={ForkyReel}
      defaultProps={defaultProps}
      fps={30}
      width={1080}
      height={1920}
      durationInFrames={300}
      calculateMetadata={({ props }) => {
        const fps = props.fps ?? 30;
        return {
          fps,
          width: props.width ?? 1080,
          height: props.height ?? 1920,
          durationInFrames: calcDurationInFrames(props, fps),
        };
      }}
    />
  );
};
