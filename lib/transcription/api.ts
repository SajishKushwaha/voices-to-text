import { TRANSCRIBE_API_URL } from "./config";
import type {
  ApiErrorResponse,
  TranscriptionResponse
} from "@/types/transcription";

export class TranscriptionApiError extends Error {
  code: string;

  constructor(message: string, code = "TRANSCRIPTION_FAILED") {
    super(message);
    this.name = "TranscriptionApiError";
    this.code = code;
  }
}

export async function transcribeAudio(
  audio: Blob,
  options: { signal?: AbortSignal } = {}
): Promise<TranscriptionResponse> {
  if (!audio.size) {
    throw new TranscriptionApiError("No audio was captured.", "EMPTY_AUDIO");
  }

  const formData = new FormData();
  const extension = getAudioExtension(audio.type);
  formData.append("audio", audio, `recording-${Date.now()}.${extension}`);

  const response = await fetch(TRANSCRIBE_API_URL, {
    method: "POST",
    body: formData,
    signal: options.signal
  });

  const payload = (await response.json().catch(() => null)) as
    | TranscriptionResponse
    | ApiErrorResponse
    | null;

  if (!response.ok || !payload?.success) {
    const errorPayload = payload as ApiErrorResponse | null;
    throw new TranscriptionApiError(
      errorPayload?.error ?? "Unable to transcribe audio.",
      errorPayload?.code ?? "TRANSCRIPTION_FAILED"
    );
  }

  return payload;
}

function getAudioExtension(mimeType: string) {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}
