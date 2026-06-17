export const TRANSCRIBE_API_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_API_URL ??
  "http://127.0.0.1:5001/api/transcribe";

export const TRANSCRIBE_WS_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_WS_URL ??
  "ws://127.0.0.1:5001/api/transcribe/stream";

export const BACKEND_API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_API_URL ?? "http://127.0.0.1:5001";

export const MAX_RECORDING_SECONDS = Number(
  process.env.NEXT_PUBLIC_MAX_RECORDING_SECONDS ?? 180
);

export const MIN_RECORDING_SECONDS = Number(
  process.env.NEXT_PUBLIC_MIN_RECORDING_SECONDS ?? 0
);

export const TRANSCRIBE_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_TRANSCRIBE_TIMEOUT_MS ?? 300000
);

export const STREAM_AUDIO_CHUNK_MS = Number(
  process.env.NEXT_PUBLIC_STREAM_AUDIO_CHUNK_MS ?? 750
);

export const STREAM_RECONNECT_MS = Number(
  process.env.NEXT_PUBLIC_STREAM_RECONNECT_MS ?? 1200
);
