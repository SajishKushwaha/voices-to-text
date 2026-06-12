"use client";

import { AlertTriangle, Check, Loader2, RefreshCcw } from "lucide-react";
import { formatClock, formatTimer } from "@/lib/transcription/time";
import type { VoiceChatMessage } from "@/types/transcription";

interface TranscriptionBubbleProps {
  message: VoiceChatMessage;
  onRetry: (message: VoiceChatMessage) => void;
}

export function TranscriptionBubble({
  message,
  onRetry
}: TranscriptionBubbleProps) {
  return (
    <article className="flex justify-end">
      <div className="w-full max-w-[86%] rounded-lg rounded-tr-sm bg-chat-bubble px-4 py-3 shadow-sm sm:max-w-[72%]">
        <audio className="mb-3 w-full" controls src={message.audioUrl}>
          <track kind="captions" />
        </audio>

        {message.status === "transcribing" && (
          <div className="flex items-center gap-2 text-sm text-chat-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Transcribing voice locally...
          </div>
        )}

        {message.status === "ready" && (
          <>
            {message.languageFallbackUsed && message.detectedLanguage && (
              <p className="mb-2 rounded-md bg-white/60 px-2 py-1 text-xs font-medium text-chat-muted">
                Auto-detected {message.detectedLanguage.toUpperCase()}, retried as{" "}
                {message.language?.toUpperCase()}.
              </p>
            )}
            <p className="whitespace-pre-wrap text-[15px] leading-6 text-chat-ink">
              {message.text}
            </p>
          </>
        )}

        {message.status === "error" && (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-sm text-red-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{message.error ?? "Transcription failed."}</span>
            </div>
            <button
              className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-chat-green"
              onClick={() => onRetry(message)}
              type="button"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        )}

        <div className="mt-2 flex flex-wrap items-center justify-end gap-2 text-[11px] text-chat-muted">
          <span>{formatTimer(message.durationSeconds)}</span>
          {message.language && <span>{message.language.toUpperCase()}</span>}
          {message.processingTime !== undefined && (
            <span>{message.processingTime.toFixed(2)}s</span>
          )}
          <span>{formatClock(message.createdAt)}</span>
          {message.status === "ready" && <Check className="h-3.5 w-3.5" />}
        </div>
      </div>
    </article>
  );
}
