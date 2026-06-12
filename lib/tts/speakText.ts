"use client";

import type { TtsApiResponse, TtsVoiceId } from "./types";

interface SpeakTextOptions {
  voiceId?: TtsVoiceId;
  signal?: AbortSignal;
  volume?: number;
}

interface SpeechRequestOptions {
  voiceId?: TtsVoiceId;
  signal?: AbortSignal;
}

const audioUrlCache = new Map<string, Promise<TtsApiResponse>>();

export class TtsClientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TtsClientError";
  }
}

export async function speakText(
  text: string,
  options: SpeakTextOptions = {}
): Promise<HTMLAudioElement> {
  const result = await requestSpeechAudio(text, options);
  const audio = new Audio(result.audioUrl);
  audio.volume = options.volume ?? 1;
  await audio.play();
  return audio;
}

export async function requestSpeechAudio(
  text: string,
  options: SpeechRequestOptions = {}
): Promise<TtsApiResponse> {
  const normalizedText = text.replace(/\s+/g, " ").trim();

  if (!normalizedText) {
    throw new TtsClientError("Nothing to speak.");
  }

  const cacheKey = createClientCacheKey(normalizedText, options.voiceId);
  const cached = audioUrlCache.get(cacheKey);

  if (cached) {
    return cached;
  }

  const request = fetch("/api/tts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text: normalizedText,
      voiceId: options.voiceId
    }),
    signal: options.signal
  })
    .then(async (response) => {
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new TtsClientError(
          payload?.error ?? "Speech generation failed. Please try again."
        );
      }

      return payload as TtsApiResponse;
    })
    .catch((error) => {
      audioUrlCache.delete(cacheKey);

      if (error instanceof TtsClientError) {
        throw error;
      }

      throw new TtsClientError("Speech service is unavailable.");
    });

  audioUrlCache.set(cacheKey, request);
  return request;
}

export function clearSpeechCache() {
  audioUrlCache.clear();
}

function createClientCacheKey(text: string, voiceId?: TtsVoiceId) {
  let hash = 2166136261;
  const input = `${voiceId ?? "default"}\0${text}`;

  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return hash.toString(16);
}
