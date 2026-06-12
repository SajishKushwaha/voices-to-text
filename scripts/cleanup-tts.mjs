import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const generatedDir = path.join(rootDir, "public", "generated", "tts");
const configuredHours = Number(process.env.TTS_AUDIO_MAX_AGE_HOURS);
const maxAgeHours = Number(process.argv[2] ?? configuredHours);
const effectiveHours =
  Number.isFinite(maxAgeHours) && maxAgeHours > 0 ? maxAgeHours : 24;
const maxAgeMs = effectiveHours * 60 * 60 * 1000;

await fs.mkdir(generatedDir, { recursive: true });

const now = Date.now();
const files = await fs.readdir(generatedDir, { withFileTypes: true });
let deletedCount = 0;

for (const file of files) {
  if (!file.isFile() || !file.name.endsWith(".wav")) {
    continue;
  }

  const filePath = path.join(generatedDir, file.name);
  const stats = await fs.stat(filePath);

  if (now - stats.mtimeMs > maxAgeMs) {
    await fs.unlink(filePath);
    deletedCount += 1;
  }
}

console.log(`Deleted ${deletedCount} generated TTS file(s).`);
