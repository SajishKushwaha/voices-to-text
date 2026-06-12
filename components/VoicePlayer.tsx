"use client";

import { Loader2, Pause, Play, RotateCcw, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { requestSpeechAudio } from "@/lib/tts/speakText";
import type { TtsVoiceId } from "@/lib/tts/types";

interface VoicePlayerProps {
  text: string;
  voiceId?: TtsVoiceId;
  title?: string;
  autoPlay?: boolean;
  className?: string;
  onError?: (error: string) => void;
}

type PlayerState = "idle" | "loading" | "ready" | "playing" | "paused" | "error";

export function VoicePlayer({
  autoPlay = false,
  className,
  onError,
  text,
  title = "Voice response",
  voiceId
}: VoicePlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState>("idle");
  const [error, setError] = useState<string | null>(null);

  const unloadAudio = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
  }, []);

  const prepareAudio = useCallback(async () => {
    if (audioRef.current) {
      return audioRef.current;
    }

    setPlayerState("loading");
    setError(null);

    try {
      const response = await requestSpeechAudio(text, { voiceId });
      const audio = new Audio(response.audioUrl);
      audioRef.current = audio;

      audio.addEventListener("ended", () => setPlayerState("ready"));
      audio.addEventListener("pause", () => {
        if (audio.currentTime > 0 && audio.currentTime < audio.duration) {
          setPlayerState("paused");
        }
      });
      audio.addEventListener("error", () => {
        setError("Unable to play generated audio.");
        setPlayerState("error");
      });

      setPlayerState("ready");
      return audio;
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Speech generation failed.";

      setError(message);
      setPlayerState("error");
      onError?.(message);
      return null;
    }
  }, [onError, text, voiceId]);

  const play = useCallback(async () => {
    const audio = await prepareAudio();

    if (!audio) {
      return;
    }

    await audio.play();
    setPlayerState("playing");
  }, [prepareAudio]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPlayerState("paused");
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    setPlayerState(audioRef.current ? "ready" : "idle");
  }, []);

  const replay = useCallback(async () => {
    const audio = await prepareAudio();

    if (!audio) {
      return;
    }

    audio.currentTime = 0;
    await audio.play();
    setPlayerState("playing");
  }, [prepareAudio]);

  useEffect(() => {
    unloadAudio();
    setPlayerState("idle");
    setError(null);
  }, [text, unloadAudio, voiceId]);

  useEffect(() => {
    if (autoPlay && text.trim()) {
      void play();
    }
  }, [autoPlay, play, text]);

  useEffect(() => {
    return () => unloadAudio();
  }, [unloadAudio]);

  const isLoading = playerState === "loading";
  const isPlaying = playerState === "playing";

  return (
    <section className={`voice-player ${className ?? ""}`.trim()}>
      <div className="voice-player__meta">
        <p className="voice-player__title">{title}</p>
        <p className="voice-player__text">{text}</p>
      </div>

      <div className="voice-player__controls">
        <button
          aria-label="Play"
          className="icon-button"
          disabled={isLoading || isPlaying}
          onClick={play}
          title="Play"
          type="button"
        >
          {isLoading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        </button>
        <button
          aria-label="Pause"
          className="icon-button"
          disabled={!isPlaying}
          onClick={pause}
          title="Pause"
          type="button"
        >
          <Pause size={18} />
        </button>
        <button
          aria-label="Stop"
          className="icon-button"
          disabled={playerState === "idle" || isLoading}
          onClick={stop}
          title="Stop"
          type="button"
        >
          <Square size={18} />
        </button>
        <button
          aria-label="Replay"
          className="icon-button"
          disabled={isLoading}
          onClick={replay}
          title="Replay"
          type="button"
        >
          <RotateCcw size={18} />
        </button>
      </div>

      <div className="voice-player__status" role="status">
        {isLoading && "Generating audio..."}
        {playerState === "error" && error && (
          <span className="voice-player__error">{error}</span>
        )}
      </div>
    </section>
  );
}
