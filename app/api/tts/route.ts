import { NextResponse } from "next/server";
import { generateSpeechAudio } from "@/lib/tts/piper";
import { TtsInputError } from "@/lib/tts/sanitize";
import { TTS_VOICES } from "@/lib/tts/voices";
import type { TtsErrorResponse, TtsRequestBody } from "@/lib/tts/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    voices: TTS_VOICES.map(({ id, label, language }) => ({
      id,
      label,
      language
    }))
  });
}

export async function POST(request: Request) {
  let body: Partial<TtsRequestBody>;

  try {
    body = (await request.json()) as Partial<TtsRequestBody>;
  } catch {
    return jsonError("Invalid JSON body.", "INVALID_JSON", 400);
  }

  try {
    const result = await generateSpeechAudio({
      text: body.text,
      voiceId: body.voiceId
    });

    return NextResponse.json(result, {
      headers: {
        "Cache-Control": "no-store"
      }
    });
  } catch (error) {
    if (error instanceof TtsInputError) {
      return jsonError(error.message, "INVALID_TTS_INPUT", 400);
    }

    const message = error instanceof Error ? error.message : "Unknown TTS error.";
    const isInstallError = message.includes("voice model is missing");

    console.error("[tts] request failed", {
      code: isInstallError ? "PIPER_NOT_READY" : "TTS_GENERATION_FAILED",
      message
    });

    return jsonError(
      isInstallError
        ? "Piper is not ready. Install the local binary and voice models first."
        : "Unable to generate speech audio.",
      isInstallError ? "PIPER_NOT_READY" : "TTS_GENERATION_FAILED",
      isInstallError ? 503 : 500
    );
  }
}

function jsonError(message: string, code: string, status: number) {
  const body: TtsErrorResponse = {
    error: message,
    code
  };

  return NextResponse.json(body, { status });
}
