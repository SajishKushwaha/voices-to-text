"use client";

import { useCallback, useRef, useState } from "react";
import {
  getHospitalWorkflowSpeechText,
  type HospitalWorkflowEvent,
  type HospitalWorkflowSpeechOptions
} from "@/lib/tts/workflow";
import { speakText } from "@/lib/tts/speakText";

export function useHospitalWorkflowTts() {
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    currentAudioRef.current?.pause();

    if (currentAudioRef.current) {
      currentAudioRef.current.currentTime = 0;
    }

    currentAudioRef.current = null;
    setIsSpeaking(false);
  }, []);

  const announceWorkflowEvent = useCallback(
    async (
      event: HospitalWorkflowEvent,
      options: HospitalWorkflowSpeechOptions = {}
    ) => {
      const text = getHospitalWorkflowSpeechText(event, options.context);

      try {
        stop();
        setError(null);
        setIsSpeaking(true);

        const audio = await speakText(text, { voiceId: options.voiceId });
        currentAudioRef.current = audio;
        audio.addEventListener("ended", () => setIsSpeaking(false), {
          once: true
        });

        return { text, audio };
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : "Unable to play workflow speech.";

        setError(message);
        setIsSpeaking(false);
        return { text, error: message };
      }
    },
    [stop]
  );

  return {
    announceWorkflowEvent,
    error,
    isSpeaking,
    stop
  };
}
