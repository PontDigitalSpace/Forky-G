import { Config } from "@remotion/cli/config";

// Vertical reel defaults; high-quality H.264 for social.
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(null); // auto
Config.setChromiumOpenGlRenderer("angle");
