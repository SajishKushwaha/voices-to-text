import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import {
  GENERATED_TTS_DIR,
  cleanupOldGeneratedAudio,
  getTtsAudioMaxAgeMs
} from "./cleanup";
import { sanitizeTtsText } from "./sanitize";
import { getVoice, getVoicePaths } from "./voices";
import type { TtsApiResponse, TtsVoiceId } from "./types";

const GENERATED_TTS_PUBLIC_PATH = "/generated/tts";
const inFlightGenerations = new Map<string, Promise<TtsApiResponse>>();
let lastCleanupAt = 0;

interface GenerateSpeechOptions {
  text: unknown;
  voiceId?: string;
}

class PiperRuntimeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PiperRuntimeError";
  }
}

export async function generateSpeechAudio({
  text,
  voiceId
}: GenerateSpeechOptions): Promise<TtsApiResponse> {
  const sanitizedText = sanitizeTtsText(text);
  const voice = getVoice(voiceId);
  const cacheKey = createCacheKey(sanitizedText, voice.id);

  void cleanupOldAudioOnInterval().catch((error) => {
    console.error("[tts] cleanup failed", error);
  });

  const existing = inFlightGenerations.get(cacheKey);

  if (existing) {
    return existing;
  }

  const generation = synthesizeWithPiper(sanitizedText, voice.id, cacheKey)
    .finally(() => {
      inFlightGenerations.delete(cacheKey);
    });

  inFlightGenerations.set(cacheKey, generation);
  return generation;
}

async function synthesizeWithPiper(
  text: string,
  voiceId: TtsVoiceId,
  cacheKey: string
): Promise<TtsApiResponse> {
  const voice = getVoice(voiceId);
  const outputFile = `${cacheKey}.wav`;
  const outputPath = path.join(GENERATED_TTS_DIR, outputFile);
  const audioUrl = `${GENERATED_TTS_PUBLIC_PATH}/${outputFile}`;

  await fs.mkdir(GENERATED_TTS_DIR, { recursive: true });

  if (await hasUsableFile(outputPath)) {
    console.info("[tts] cache hit", { cacheKey, voiceId });
    return createResponse({ audioUrl, cacheKey, voiceId, text, cached: true });
  }

  const { modelPath, configPath } = getVoicePaths(voice);
  await assertVoiceInstalled(modelPath, configPath);

  const piperBin = await resolvePiperBinary();
  const tempOutputPath = path.join(
    GENERATED_TTS_DIR,
    `${cacheKey}.${randomUUID()}.tmp.wav`
  );

  console.info("[tts] generating audio", {
    cacheKey,
    textLength: text.length,
    voiceId
  });

  await runPiper({
    configPath,
    modelPath,
    outputPath: tempOutputPath,
    piperBin,
    text
  });

  await fs.rename(tempOutputPath, outputPath);

  return createResponse({ audioUrl, cacheKey, voiceId, text, cached: false });
}

function createResponse({
  audioUrl,
  cacheKey,
  cached,
  text,
  voiceId
}: {
  audioUrl: string;
  cacheKey: string;
  cached: boolean;
  text: string;
  voiceId: TtsVoiceId;
}): TtsApiResponse {
  return {
    audioUrl,
    cacheKey,
    cached,
    voiceId,
    textLength: text.length,
    expiresInSeconds: Math.floor(getTtsAudioMaxAgeMs() / 1000)
  };
}

function createCacheKey(text: string, voiceId: TtsVoiceId) {
  return createHash("sha256")
    .update(`${voiceId}\0${text}`)
    .digest("hex")
    .slice(0, 40);
}

async function resolvePiperBinary() {
  const configured = process.env.PIPER_BIN?.trim();

  if (configured) {
    const resolved = path.isAbsolute(configured)
      ? configured
      : path.resolve(/* turbopackIgnore: true */ process.cwd(), configured);

    if (await hasExecutable(resolved)) {
      return resolved;
    }
  }

  const localPythonBinary = path.join(
    /* turbopackIgnore: true */ process.cwd(),
    ".venv",
    process.platform === "win32" ? "Scripts" : "bin",
    process.platform === "win32" ? "piper.exe" : "piper"
  );

  if (await hasExecutable(localPythonBinary)) {
    return localPythonBinary;
  }

  const localBinary = path.join(
    /* turbopackIgnore: true */ process.cwd(),
    "bin",
    "piper",
    process.platform === "win32" ? "piper.exe" : "piper"
  );

  if (await hasExecutable(localBinary)) {
    return localBinary;
  }

  const nestedLocalBinary = path.join(
    /* turbopackIgnore: true */ process.cwd(),
    "bin",
    "piper",
    "piper",
    process.platform === "win32" ? "piper.exe" : "piper"
  );

  if (await hasExecutable(nestedLocalBinary)) {
    return nestedLocalBinary;
  }

  return process.platform === "win32" ? "piper.exe" : "piper";
}

async function assertVoiceInstalled(modelPath: string, configPath: string) {
  const [modelExists, configExists] = await Promise.all([
    hasUsableFile(modelPath),
    hasUsableFile(configPath)
  ]);

  if (!modelExists || !configExists) {
    throw new PiperRuntimeError(
      "Piper voice model is missing. Run `npm run piper:install` before using TTS."
    );
  }
}

async function hasExecutable(filePath: string) {
  try {
    await fs.access(filePath, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function hasUsableFile(filePath: string) {
  try {
    const stats = await fs.stat(filePath);
    return stats.isFile() && stats.size > 44;
  } catch {
    return false;
  }
}

async function runPiper({
  configPath,
  modelPath,
  outputPath,
  piperBin,
  text
}: {
  configPath: string;
  modelPath: string;
  outputPath: string;
  piperBin: string;
  text: string;
}) {
  const timeoutMs = getGenerationTimeoutMs();

  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      piperBin,
      ["-m", modelPath, "-c", configPath, "-f", outputPath],
      {
        shell: false,
        stdio: ["pipe", "ignore", "pipe"]
      }
    );

    let stderr = "";
    let settled = false;

    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      rejectOnce(
        new PiperRuntimeError(`Piper generation timed out after ${timeoutMs}ms.`)
      );
    }, timeoutMs);

    function rejectOnce(error: Error) {
      if (!settled) {
        settled = true;
        clearTimeout(timeout);
        reject(error);
      }
    }

    child.stderr.on("data", (chunk: Buffer) => {
      stderr = `${stderr}${chunk.toString("utf8")}`.slice(-8000);
    });

    child.on("error", (error) => {
      rejectOnce(new PiperRuntimeError(`Unable to start Piper: ${error.message}`));
    });

    child.on("close", (code) => {
      if (settled) {
        return;
      }

      settled = true;
      clearTimeout(timeout);

      if (code === 0) {
        resolve();
        return;
      }

      reject(
        new PiperRuntimeError(
          `Piper exited with code ${code ?? "unknown"}${stderr ? `: ${stderr}` : "."}`
        )
      );
    });

    child.stdin.end(`${text}\n`, "utf8");
  }).catch(async (error) => {
    await fs.rm(outputPath, { force: true });
    throw error;
  });
}

function getGenerationTimeoutMs() {
  const configured = Number(process.env.TTS_GENERATION_TIMEOUT_MS);
  return Number.isFinite(configured) && configured > 1000 ? configured : 15000;
}

async function cleanupOldAudioOnInterval() {
  const configuredMinutes = Number(process.env.TTS_CLEANUP_INTERVAL_MINUTES);
  const intervalMs =
    (Number.isFinite(configuredMinutes) && configuredMinutes > 0
      ? configuredMinutes
      : 5) *
    60 *
    1000;

  if (Date.now() - lastCleanupAt < intervalMs) {
    return;
  }

  lastCleanupAt = Date.now();
  const deletedCount = await cleanupOldGeneratedAudio();

  if (deletedCount > 0) {
    console.info("[tts] deleted old generated audio", { deletedCount });
  }
}
