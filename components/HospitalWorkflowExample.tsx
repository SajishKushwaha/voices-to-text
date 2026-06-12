"use client";

import { useMemo, useState } from "react";
import { VoicePlayer } from "./VoicePlayer";
import { useHospitalWorkflowTts } from "@/hooks/useHospitalWorkflowTts";
import {
  getHospitalWorkflowSpeechText,
  type HospitalWorkflowEvent
} from "@/lib/tts/workflow";
import type { TtsVoiceId } from "@/lib/tts/types";

const workflowEvents: Array<{
  event: HospitalWorkflowEvent;
  label: string;
}> = [
  { event: "appointmentBooked", label: "Appointment booked" },
  { event: "appointmentCancelled", label: "Appointment cancelled" },
  { event: "appointmentRescheduled", label: "Appointment rescheduled" },
  { event: "patientCheckedIn", label: "Patient checked-in" },
  { event: "consultationCompleted", label: "Consultation completed" },
  { event: "prescriptionGenerated", label: "Prescription generated" },
  { event: "billingCompleted", label: "Billing completed" }
];

const voiceOptions: Array<{ id: TtsVoiceId; label: string }> = [
  { id: "en_US-lessac-medium", label: "English - Lessac" },
  { id: "hi_IN-pratham-medium", label: "Hindi - Pratham" },
  { id: "hi_IN-priyamvada-medium", label: "Hindi - Priyamvada" }
];

export function HospitalWorkflowExample() {
  const [voiceId, setVoiceId] = useState<TtsVoiceId>("en_US-lessac-medium");
  const [lastText, setLastText] = useState(
    getHospitalWorkflowSpeechText("appointmentBooked", {
      appointmentTime: "10:30 AM",
      doctorName: "Rao",
      patientName: "Ananya"
    })
  );
  const { announceWorkflowEvent, error, isSpeaking } = useHospitalWorkflowTts();

  const demoContext = useMemo(
    () => ({
      amount: "1200 rupees",
      appointmentTime: "10:30 AM",
      doctorName: "Rao",
      patientName: "Ananya"
    }),
    []
  );

  async function handleWorkflowAction(event: HospitalWorkflowEvent) {
    const result = await announceWorkflowEvent(event, {
      voiceId,
      context: demoContext
    });

    setLastText(result.text);
  }

  return (
    <div className="workflow-layout">
      <section className="panel">
        <h2>Workflow actions</h2>
        <div className="workflow-grid">
          {workflowEvents.map(({ event, label }) => (
            <button
              className="workflow-button"
              disabled={isSpeaking}
              key={event}
              onClick={() => void handleWorkflowAction(event)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <aside className="panel">
        <h2>Voice output</h2>
        <select
          aria-label="Voice"
          className="voice-select"
          onChange={(event) => setVoiceId(event.target.value as TtsVoiceId)}
          value={voiceId}
        >
          {voiceOptions.map((voice) => (
            <option key={voice.id} value={voice.id}>
              {voice.label}
            </option>
          ))}
        </select>
        <VoicePlayer
          className="voice-player--panel"
          text={lastText}
          title="Last generated response"
          voiceId={voiceId}
        />
        {error && <p className="voice-player__error">{error}</p>}
      </aside>
    </div>
  );
}
