"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_RECORDING_SECONDS } from "@/lib/transcription/config";
import { getSupportedAudioMimeType } from "@/lib/transcription/media";
import type { RecorderStatus } from "@/types/transcription";

interface UseVoiceRecorderOptions {
  onRecordingComplete?: (audio: Blob, durationSeconds: number) => void;
}

export function useVoiceRecorder({
  onRecordingComplete
}: UseVoiceRecorderOptions = {}) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [durationSeconds, setDurationSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [permissionState, setPermissionState] = useState<
    PermissionState | "unsupported" | "unknown"
  >("unknown");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);
  const durationRef = useRef(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const reset = useCallback(() => {
    clearTimer();
    stopStream();
    chunksRef.current = [];
    durationRef.current = 0;
    setDurationSeconds(0);
    setStatus("idle");
    setError(null);
  }, [clearTimer, stopStream]);

  const startTimer = useCallback(() => {
    clearTimer();
    timerRef.current = window.setInterval(() => {
      durationRef.current += 1;
      setDurationSeconds(durationRef.current);

      if (durationRef.current >= MAX_RECORDING_SECONDS) {
        recorderRef.current?.stop();
      }
    }, 1000);
  }, [clearTimer]);

  const refreshPermission = useCallback(async () => {
    if (!navigator.permissions?.query) {
      setPermissionState("unknown");
      return;
    }

    try {
      const permission = await navigator.permissions.query({
        name: "microphone" as PermissionName
      });
      setPermissionState(permission.state);
      permission.onchange = () => setPermissionState(permission.state);
    } catch {
      setPermissionState("unknown");
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Audio recording is not supported in this browser.");
      setPermissionState("unsupported");
      setStatus("error");
      return;
    }

    try {
      setStatus("requesting-permission");
      setError(null);
      chunksRef.current = [];
      durationRef.current = 0;
      setDurationSeconds(0);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true
        }
      });
      streamRef.current = stream;
      setPermissionState("granted");

      const mimeType = getSupportedAudioMimeType();
      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      );
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setError("Recording failed. Please try again.");
        setStatus("error");
        clearTimer();
        stopStream();
      };

      recorder.onstop = () => {
        clearTimer();
        stopStream();
        const audio = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm"
        });

        if (audio.size > 0) {
          onRecordingComplete?.(audio, durationRef.current);
        }

        chunksRef.current = [];
        durationRef.current = 0;
        setDurationSeconds(0);
        setStatus("idle");
      };

      recorder.start(250);
      setStatus("recording");
      startTimer();
    } catch (caughtError) {
      const message =
        caughtError instanceof DOMException && caughtError.name === "NotAllowedError"
          ? "Microphone permission was denied."
          : "Could not access the microphone.";

      setError(message);
      setPermissionState("denied");
      setStatus("error");
      clearTimer();
      stopStream();
    }
  }, [clearTimer, onRecordingComplete, startTimer, stopStream]);

  const pauseRecording = useCallback(() => {
    const recorder = recorderRef.current;

    if (recorder?.state === "recording") {
      recorder.pause();
      clearTimer();
      setStatus("paused");
    }
  }, [clearTimer]);

  const resumeRecording = useCallback(() => {
    const recorder = recorderRef.current;

    if (recorder?.state === "paused") {
      recorder.resume();
      startTimer();
      setStatus("recording");
    }
  }, [startTimer]);

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;

    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
      return;
    }

    clearTimer();
    stopStream();
    setStatus("stopped");
  }, [clearTimer, stopStream]);

  useEffect(() => {
    void refreshPermission();

    return () => {
      clearTimer();
      stopStream();
    };
  }, [clearTimer, refreshPermission, stopStream]);

  return {
    durationSeconds,
    error,
    isPaused: status === "paused",
    isRecording: status === "recording",
    pauseRecording,
    permissionState,
    refreshPermission,
    reset,
    resumeRecording,
    startRecording,
    status,
    stopRecording
  };
}
