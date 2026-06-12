import path from "node:path";
import manifest from "@/voices/manifest.json";
import type { TtsVoice, TtsVoiceId } from "./types";

export const TTS_VOICES = manifest.voices as TtsVoice[];

export const DEFAULT_TTS_VOICE_ID = getConfiguredDefaultVoiceId();

function getConfiguredDefaultVoiceId(): TtsVoiceId {
  const configuredVoiceId = process.env.TTS_DEFAULT_VOICE_ID as
    | TtsVoiceId
    | undefined;

  if (configuredVoiceId && isSupportedVoiceId(configuredVoiceId)) {
    return configuredVoiceId;
  }

  return "en_US-lessac-medium";
}

export function isSupportedVoiceId(voiceId: string): voiceId is TtsVoiceId {
  return TTS_VOICES.some((voice) => voice.id === voiceId);
}

export function getVoice(voiceId?: string): TtsVoice {
  const resolvedVoiceId =
    voiceId && isSupportedVoiceId(voiceId) ? voiceId : DEFAULT_TTS_VOICE_ID;
  const voice = TTS_VOICES.find((candidate) => candidate.id === resolvedVoiceId);

  if (!voice) {
    throw new Error(`Unsupported TTS voice: ${resolvedVoiceId}`);
  }

  return voice;
}

export function getVoicePaths(voice: TtsVoice) {
  const voicesDir = path.resolve(
    /* turbopackIgnore: true */ process.cwd(),
    "voices"
  );
  const modelPath = path.resolve(voicesDir, voice.modelFile);
  const configPath = path.resolve(voicesDir, voice.configFile);

  if (!modelPath.startsWith(`${voicesDir}${path.sep}`)) {
    throw new Error("Resolved Piper model path is outside the voices directory.");
  }

  if (!configPath.startsWith(`${voicesDir}${path.sep}`)) {
    throw new Error("Resolved Piper config path is outside the voices directory.");
  }

  return { configPath, modelPath };
}
