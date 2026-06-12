"use client";

import { clsx } from "clsx";
import { Loader2, Mic, Pause, Play, RotateCcw, Send, Square } from "lucide-react";
import { formatTimer } from "@/lib/transcription/time";
import type { RecorderStatus } from "@/types/transcription";
import { Waveform } from "./Waveform";

interface RecorderControlsProps {
  durationSeconds: number;
  isUploading: boolean;
  onPause: () => void;
  onReset: () => void;
  onResume: () => void;
  onStart: () => void;
  onStop: () => void;
  status: RecorderStatus;
}

export function RecorderControls({
  durationSeconds,
  isUploading,
  onPause,
  onReset,
  onResume,
  onStart,
  onStop,
  status
}: RecorderControlsProps) {
  const isRecording = status === "recording";
  const isPaused = status === "paused";
  const isCapturing = isRecording || isPaused;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-soft">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-chat-slate">
            {isCapturing ? "Voice message" : "Ready to record"}
          </p>
          <p className="text-xs text-chat-muted">
            {isUploading
              ? "Transcribing locally with Faster-Whisper"
              : "Audio is processed by your Flask server"}
          </p>
        </div>
        <div className="rounded-full bg-slate-100 px-3 py-1 font-mono text-sm font-semibold text-chat-slate">
          {formatTimer(durationSeconds)}
        </div>
      </div>

      <Waveform active={isRecording || isUploading} paused={isPaused} />

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        {!isCapturing && (
          <button
            className="inline-flex h-12 items-center gap-2 rounded-full bg-chat-green px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isUploading || status === "requesting-permission"}
            onClick={onStart}
            type="button"
          >
            {status === "requesting-permission" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
            Start Recording
          </button>
        )}

        {isRecording && (
          <button className={controlButton()} onClick={onPause} type="button">
            <Pause className="h-4 w-4" />
            Pause
          </button>
        )}

        {isPaused && (
          <button className={controlButton()} onClick={onResume} type="button">
            <Play className="h-4 w-4" />
            Resume
          </button>
        )}

        {isCapturing && (
          <button
            className="inline-flex h-12 items-center gap-2 rounded-full bg-chat-slate px-5 text-sm font-semibold text-white transition hover:bg-slate-700"
            onClick={onStop}
            type="button"
          >
            <Square className="h-4 w-4" />
            Stop & Send
          </button>
        )}

        <button
          className={clsx(
            controlButton(),
            "disabled:cursor-not-allowed disabled:opacity-50"
          )}
          disabled={isUploading || isCapturing || durationSeconds === 0}
          onClick={onReset}
          type="button"
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </button>

        {isUploading && (
          <div className="inline-flex h-12 items-center gap-2 rounded-full bg-slate-100 px-4 text-sm font-medium text-chat-muted">
            <Send className="h-4 w-4" />
            Uploading
          </div>
        )}
      </div>
    </section>
  );
}

function controlButton() {
  return "inline-flex h-12 items-center gap-2 rounded-full border border-slate-200 bg-white px-5 text-sm font-semibold text-chat-slate transition hover:border-chat-green hover:text-chat-green";
}
