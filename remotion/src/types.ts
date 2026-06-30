// Data contract between the Python agent and the Remotion edit.
// Everything the edit needs is passed as inputProps (no hardcoded content).

export type Scene = {
  // Path RELATIVE to remotion/public/ (the Python bridge stages assets there
  // and the composition wraps it in staticFile()).
  src: string;
  kind: "video" | "image";
  durationInSeconds: number;
  text?: string; // on-screen caption for this beat ("" = none)
  note?: string; // optional pacing/camera cue (not rendered)
};

export type Brand = {
  name: string; // "La Medusa"
  handle?: string; // "lamedusarestaurant.ca"
  primaryColor: string; // accent, e.g. gold "#d6b646"
  bgColor: string; // deep background, e.g. "#1d1c1a"
  textColor: string; // light text, e.g. cream "#f5f0e8"
  titleFont?: "PlayfairDisplay" | "Montserrat";
  bodyFont?: "PlayfairDisplay" | "Montserrat";
  logoSrc?: string | null; // relative to public/, optional
};

export type ReelProps = {
  brand: Brand;
  scenes: Scene[];
  voiceover?: string | null; // relative to public/, optional
  music?: string | null; // relative to public/, optional
  musicVolume?: number; // 0..1, default 0.12 under VO
  intro?: { title: string; subtitle?: string } | null;
  outro?: { title: string; cta?: string } | null;
  fps?: number; // default 30
  width?: number; // default 1080
  height?: number; // default 1920
};
