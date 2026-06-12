export const TRANSCRIBE_API_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_API_URL ??
  "http://127.0.0.1:5001/api/transcribe";

export const MAX_RECORDING_SECONDS = Number(
  process.env.NEXT_PUBLIC_MAX_RECORDING_SECONDS ?? 180
);
