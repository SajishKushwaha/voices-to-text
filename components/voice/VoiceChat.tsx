"use client";

import { useCallback, useMemo, useState } from "react";
import { Lock, MessageCircle, Server } from "lucide-react";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { transcribeAudio } from "@/lib/transcription/api";
import type { VoiceChatMessage } from "@/types/transcription";
import { PermissionNotice } from "./PermissionNotice";
import { RecorderControls } from "./RecorderControls";
import { TranscriptionBubble } from "./TranscriptionBubble";

export function VoiceChat() {
  const [messages, setMessages] = useState<VoiceChatMessage[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const uploadAndTranscribe = useCallback(async (message: VoiceChatMessage) => {
    setIsUploading(true);

    try {
      const result = await transcribeAudio(message.audioBlob);

      setMessages((current) =>
        current.map((item) =>
          item.id === message.id
            ? {
                ...item,
                detectedLanguage: result.detectedLanguage,
                language: result.language,
                languageFallbackUsed: result.languageFallbackUsed,
                processingTime: result.processingTime,
                status: "ready",
                text: result.text || "(No speech detected)"
              }
            : item
        )
      );
    } catch (caughtError) {
      const error =
        caughtError instanceof Error
          ? caughtError.message
          : "Transcription failed.";

      setMessages((current) =>
        current.map((item) =>
          item.id === message.id ? { ...item, error, status: "error" } : item
        )
      );
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleRecordingComplete = useCallback(
    (audioBlob: Blob, durationSeconds: number) => {
      const message: VoiceChatMessage = {
        id: crypto.randomUUID(),
        audioBlob,
        audioUrl: URL.createObjectURL(audioBlob),
        createdAt: new Date().toISOString(),
        durationSeconds,
        status: "transcribing"
      };

      setMessages((current) => [...current, message]);
      void uploadAndTranscribe(message);
    },
    [uploadAndTranscribe]
  );

  const recorder = useVoiceRecorder({
    onRecordingComplete: handleRecordingComplete
  });

  const retryMessage = useCallback(
    (message: VoiceChatMessage) => {
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id
            ? { ...item, error: undefined, status: "transcribing" }
            : item
        )
      );
      void uploadAndTranscribe(message);
    },
    [uploadAndTranscribe]
  );

  const helperText = useMemo(() => {
    if (recorder.status === "paused") {
      return "Recording paused. Resume when you are ready.";
    }

    if (recorder.status === "recording") {
      return "Recording now. Stop to send the audio for transcription.";
    }

    return "Tap record, speak naturally in English or Hindi, then stop.";
  }, [recorder.status]);

  return (
    <div className="mx-auto grid min-h-[calc(100vh-3rem)] w-full max-w-6xl grid-rows-[auto_1fr_auto] overflow-hidden rounded-lg border border-white/70 bg-chat-panel shadow-soft">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-chat-green px-4 py-4 text-white sm:px-6">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-white/15">
            <MessageCircle className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold sm:text-xl">Local Voice Chat</h1>
            <p className="text-xs text-white/80 sm:text-sm">
              Next.js recorder + Flask + Faster-Whisper
            </p>
          </div>
        </div>
        <div className="hidden items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold sm:flex">
          <Lock className="h-3.5 w-3.5" />
          Zero paid APIs
        </div>
      </header>

      <section className="overflow-y-auto bg-[linear-gradient(135deg,#e5ddd5_0%,#eef5f2_100%)] px-4 py-5 sm:px-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          <div className="self-center rounded-full bg-white/75 px-4 py-2 text-center text-xs font-medium text-chat-muted shadow-sm">
            <span className="inline-flex items-center gap-2">
              <Server className="h-3.5 w-3.5" />
              Audio stays on your infrastructure
            </span>
          </div>

          {messages.length === 0 && (
            <div className="mx-auto mt-10 max-w-md rounded-lg bg-white/80 p-5 text-center shadow-sm">
              <h2 className="text-base font-bold text-chat-slate">
                Start a voice message
              </h2>
              <p className="mt-2 text-sm leading-6 text-chat-muted">
                Your browser records audio, Flask transcribes it with a local
                Faster-Whisper model, and the text appears here as a chat bubble.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <TranscriptionBubble
              key={message.id}
              message={message}
              onRetry={retryMessage}
            />
          ))}
        </div>
      </section>

      <footer className="space-y-3 border-t border-slate-200 bg-slate-50 p-4 sm:p-5">
        <div className="mx-auto max-w-4xl space-y-3">
          <PermissionNotice
            error={recorder.error}
            permissionState={recorder.permissionState}
          />
          <RecorderControls
            durationSeconds={recorder.durationSeconds}
            isUploading={isUploading}
            onPause={recorder.pauseRecording}
            onReset={recorder.reset}
            onResume={recorder.resumeRecording}
            onStart={recorder.startRecording}
            onStop={recorder.stopRecording}
            status={recorder.status}
          />
          <p className="text-center text-xs text-chat-muted">{helperText}</p>
        </div>
      </footer>
    </div>
  );
}
