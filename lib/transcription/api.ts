import { TRANSCRIBE_API_URL, TRANSCRIBE_TIMEOUT_MS } from "./config";
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
  options: { language?: string; signal?: AbortSignal; task?: string } = {}
): Promise<TranscriptionResponse> {
  if (!audio.size) {
    throw new TranscriptionApiError("No audio was captured.", "EMPTY_AUDIO");
  }

  const formData = new FormData();
  const extension = getAudioExtension(audio.type);
  formData.append("audio", audio, `recording-${Date.now()}.${extension}`);
  formData.append("language", options.language ?? "auto");
  formData.append("task", options.task ?? "transcribe");

  let response: Response;
  const timeoutController = new AbortController();
  const timeoutId = window.setTimeout(
    () => timeoutController.abort("timeout"),
    TRANSCRIBE_TIMEOUT_MS
  );
  const signal = combineAbortSignals(options.signal, timeoutController.signal);

  try {
    response = await fetch(TRANSCRIBE_API_URL, {
      method: "POST",
      body: formData,
      signal
    });
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }

    if (timeoutController.signal.aborted) {
      throw new TranscriptionApiError(
        "Transcription timed out. Try a shorter recording or restart the local backend.",
        "TRANSCRIPTION_TIMEOUT"
      );
    }

    throw new TranscriptionApiError(
      getBackendUnreachableMessage(),
      "BACKEND_UNREACHABLE"
    );
  } finally {
    window.clearTimeout(timeoutId);
  }

  const clonedResponse = response.clone();
  const payload = (await response.json().catch(() => null)) as
    | TranscriptionResponse
    | ApiErrorResponse
    | { detail?: unknown }
    | null;

  const succeeded = Boolean(
    payload && "success" in payload && payload.success === true
  );

  if (!response.ok || !succeeded) {
    const errorPayload = payload as ApiErrorResponse | null;
    const rawBody = await clonedResponse.text().catch(() => null);
    console.error(
      "Transcription API responded with error",
      response.status,
      errorPayload,
      rawBody
    );
    throw new TranscriptionApiError(
      getErrorMessage(errorPayload),
      errorPayload?.code ?? "TRANSCRIPTION_FAILED"
    );
  }

  return payload as TranscriptionResponse;
}

function combineAbortSignals(
  externalSignal: AbortSignal | undefined,
  timeoutSignal: AbortSignal
) {
  if (!externalSignal) return timeoutSignal;
  return AbortSignal.any([externalSignal, timeoutSignal]);
}

function getAudioExtension(mimeType: string) {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function getErrorMessage(payload: ApiErrorResponse | null) {
  if (payload?.error) {
    return payload.error;
  }

  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    return "Invalid transcription upload.";
  }

  return "Unable to transcribe audio.";
}

function getBackendUnreachableMessage() {
  const isLocalBackend =
    TRANSCRIBE_API_URL.includes("127.0.0.1") ||
    TRANSCRIBE_API_URL.includes("localhost");

  if (isLocalBackend) {
    return `Cannot reach transcription backend at ${TRANSCRIBE_API_URL}. Start it with npm run dev:flask.`;
  }

  return `Cannot reach transcription backend at ${TRANSCRIBE_API_URL}. Deploy or restart the backend service, then try again.`;
}
