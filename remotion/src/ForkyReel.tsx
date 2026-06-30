import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import type { Brand, ReelProps, Scene } from "./types";

const playfair = loadPlayfair();
const montserrat = loadMontserrat();

export const TRANSITION_FRAMES = 12;
const INTRO_SECONDS = 1.6;
const OUTRO_SECONDS = 2.4;

const fontFor = (b: Brand, which: "title" | "body") => {
  const pick = which === "title" ? b.titleFont ?? "PlayfairDisplay" : b.bodyFont ?? "Montserrat";
  return pick === "PlayfairDisplay" ? playfair.fontFamily : montserrat.fontFamily;
};

// ---- duration math (shared with Root.calculateMetadata) -------------------
export const calcDurationInFrames = (props: ReelProps, fps: number): number => {
  const segs: number[] = [];
  if (props.intro) segs.push(Math.round(INTRO_SECONDS * fps));
  for (const s of props.scenes) segs.push(Math.round(s.durationInSeconds * fps));
  if (props.outro) segs.push(Math.round(OUTRO_SECONDS * fps));
  const total = segs.reduce((a, b) => a + b, 0);
  const overlaps = Math.max(0, segs.length - 1) * TRANSITION_FRAMES;
  return Math.max(1, total - overlaps);
};

// ---- a single scene clip with Ken Burns + animated caption ----------------
const SceneClip: React.FC<{ scene: Scene; brand: Brand; durationInFrames: number }> = ({
  scene,
  brand,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  // slow, classy zoom (Ken Burns)
  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.12], {
    extrapolateRight: "clamp",
  });
  const src = staticFile(scene.src);
  return (
    <AbsoluteFill style={{ backgroundColor: brand.bgColor, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        {scene.kind === "video" ? (
          <OffthreadVideo src={src} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        )}
      </AbsoluteFill>
      {/* cinematic vignette top+bottom so captions read */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.78) 100%)",
        }}
      />
      {scene.text ? <Caption text={scene.text} brand={brand} durationInFrames={durationInFrames} /> : null}
    </AbsoluteFill>
  );
};

const Caption: React.FC<{ text: string; brand: Brand; durationInFrames: number }> = ({
  text,
  brand,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 18 });
  const exit = interpolate(frame, [durationInFrames - 14, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(enter, [0, 1], [60, 0]);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 280 }}>
      <div
        style={{
          opacity: Math.min(enter, exit),
          transform: `translateY(${y}px)`,
          maxWidth: 900,
          margin: "0 60px",
          padding: "24px 34px",
          background: "rgba(15,14,13,0.55)",
          borderLeft: `8px solid ${brand.primaryColor}`,
          borderRadius: 10,
          backdropFilter: "blur(6px)",
        }}
      >
        <span
          style={{
            fontFamily: fontFor(brand, "title"),
            color: brand.textColor,
            fontSize: 56,
            lineHeight: 1.18,
            fontWeight: 600,
            textShadow: "0 2px 18px rgba(0,0,0,0.6)",
            display: "block",
            textAlign: "center",
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};

const IntroCard: React.FC<{ brand: Brand; title: string; subtitle?: string }> = ({
  brand,
  title,
  subtitle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 26 });
  const letter = interpolate(reveal, [0, 1], [18, 4]);
  const lineW = interpolate(reveal, [0, 1], [0, 220]);
  return (
    <AbsoluteFill
      style={{
        backgroundColor: brand.bgColor,
        justifyContent: "center",
        alignItems: "center",
        gap: 28,
      }}
    >
      <span
        style={{
          fontFamily: fontFor(brand, "title"),
          color: brand.primaryColor,
          fontSize: 96,
          fontWeight: 700,
          letterSpacing: letter,
          opacity: reveal,
          textAlign: "center",
        }}
      >
        {title}
      </span>
      <div style={{ width: lineW, height: 3, background: brand.primaryColor, opacity: reveal }} />
      {subtitle ? (
        <span
          style={{
            fontFamily: fontFor(brand, "body"),
            color: brand.textColor,
            fontSize: 36,
            letterSpacing: 2,
            opacity: interpolate(reveal, [0.4, 1], [0, 0.9], { extrapolateLeft: "clamp" }),
            textTransform: "uppercase",
          }}
        >
          {subtitle}
        </span>
      ) : null}
    </AbsoluteFill>
  );
};

const OutroCard: React.FC<{ brand: Brand; title: string; cta?: string }> = ({ brand, title, cta }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const reveal = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 24 });
  return (
    <AbsoluteFill
      style={{ backgroundColor: brand.bgColor, justifyContent: "center", alignItems: "center", gap: 30 }}
    >
      <span
        style={{
          fontFamily: fontFor(brand, "title"),
          color: brand.primaryColor,
          fontSize: 84,
          fontWeight: 700,
          opacity: reveal,
          transform: `translateY(${interpolate(reveal, [0, 1], [30, 0])}px)`,
          textAlign: "center",
        }}
      >
        {title}
      </span>
      {cta ? (
        <span
          style={{
            fontFamily: fontFor(brand, "body"),
            color: brand.textColor,
            fontSize: 40,
            opacity: interpolate(reveal, [0.4, 1], [0, 1], { extrapolateLeft: "clamp" }),
            textAlign: "center",
          }}
        >
          {cta}
        </span>
      ) : null}
      {brand.handle ? (
        <span
          style={{
            fontFamily: fontFor(brand, "body"),
            color: brand.primaryColor,
            fontSize: 30,
            letterSpacing: 2,
            opacity: interpolate(reveal, [0.6, 1], [0, 0.85], { extrapolateLeft: "clamp" }),
          }}
        >
          {brand.handle}
        </span>
      ) : null}
    </AbsoluteFill>
  );
};

// persistent watermark (small, bottom-right) over the whole reel
const Watermark: React.FC<{ brand: Brand }> = ({ brand }) => (
  <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", padding: 44 }}>
    <span
      style={{
        fontFamily: fontFor(brand, "body"),
        color: brand.textColor,
        opacity: 0.72,
        fontSize: 26,
        letterSpacing: 1,
        textShadow: "0 2px 10px rgba(0,0,0,0.7)",
      }}
    >
      {brand.name}
    </span>
  </AbsoluteFill>
);

export const ForkyReel: React.FC<ReelProps> = (props) => {
  const { fps } = useVideoConfig();
  const { brand, scenes, intro, outro, voiceover, music } = props;
  const introFrames = intro ? Math.round(INTRO_SECONDS * fps) : 0;
  const t = linearTiming({ durationInFrames: TRANSITION_FRAMES });

  return (
    <AbsoluteFill style={{ backgroundColor: brand.bgColor }}>
      <TransitionSeries>
        {intro ? (
          <TransitionSeries.Sequence durationInFrames={introFrames}>
            <IntroCard brand={brand} title={intro.title} subtitle={intro.subtitle} />
          </TransitionSeries.Sequence>
        ) : null}
        {intro ? <TransitionSeries.Transition presentation={fade()} timing={t} /> : null}

        {scenes.flatMap((scene, i) => {
          const d = Math.round(scene.durationInSeconds * fps);
          const nodes = [
            <TransitionSeries.Sequence key={`s${i}`} durationInFrames={d}>
              <SceneClip scene={scene} brand={brand} durationInFrames={d} />
            </TransitionSeries.Sequence>,
          ];
          if (i < scenes.length - 1 || outro) {
            nodes.push(<TransitionSeries.Transition key={`t${i}`} presentation={fade()} timing={t} />);
          }
          return nodes;
        })}

        {outro ? (
          <TransitionSeries.Sequence durationInFrames={Math.round(OUTRO_SECONDS * fps)}>
            <OutroCard brand={brand} title={outro.title} cta={outro.cta} />
          </TransitionSeries.Sequence>
        ) : null}
      </TransitionSeries>

      {/* audio: voiceover starts when the scenes start (after intro); music under it */}
      {music ? <Audio loop src={staticFile(music)} volume={props.musicVolume ?? 0.12} /> : null}
      {voiceover ? (
        <Sequence from={introFrames}>
          <Audio src={staticFile(voiceover)} />
        </Sequence>
      ) : null}

      <Watermark brand={brand} />
    </AbsoluteFill>
  );
};
