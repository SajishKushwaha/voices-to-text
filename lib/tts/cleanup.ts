import "server-only";

import fs from "node:fs/promises";
import path from "node:path";

export const GENERATED_TTS_DIR = path.join(
  /* turbopackIgnore: true */ process.cwd(),
  "public",
  "generated",
  "tts"
);

export function getTtsAudioMaxAgeMs() {
  const configuredHours = Number(process.env.TTS_AUDIO_MAX_AGE_HOURS);
  const hours =
    Number.isFinite(configuredHours) && configuredHours > 0
      ? configuredHours
      : 24;

  return hours * 60 * 60 * 1000;
}

export async function cleanupOldGeneratedAudio(maxAgeMs = getTtsAudioMaxAgeMs()) {
  await fs.mkdir(GENERATED_TTS_DIR, { recursive: true });

  const now = Date.now();
  const files = await fs.readdir(GENERATED_TTS_DIR, { withFileTypes: true });
  const deletions = files
    .filter((file) => file.isFile() && file.name.endsWith(".wav"))
    .map(async (file) => {
      const filePath = path.join(GENERATED_TTS_DIR, file.name);
      const stats = await fs.stat(filePath);

      if (now - stats.mtimeMs > maxAgeMs) {
        await fs.unlink(filePath);
        return file.name;
      }

      return null;
    });

  const deleted = await Promise.all(deletions);
  return deleted.filter(Boolean).length;
}
