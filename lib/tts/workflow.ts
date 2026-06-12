import type { TtsVoiceId } from "./types";

export type HospitalWorkflowEvent =
  | "appointmentBooked"
  | "appointmentCancelled"
  | "appointmentRescheduled"
  | "patientCheckedIn"
  | "consultationCompleted"
  | "prescriptionGenerated"
  | "billingCompleted";

export interface HospitalWorkflowSpeechContext {
  patientName?: string;
  doctorName?: string;
  appointmentTime?: string;
  amount?: string;
}

export interface HospitalWorkflowSpeechOptions {
  voiceId?: TtsVoiceId;
  context?: HospitalWorkflowSpeechContext;
}

const workflowMessages: Record<
  HospitalWorkflowEvent,
  (context: HospitalWorkflowSpeechContext) => string
> = {
  appointmentBooked: ({ patientName, doctorName, appointmentTime }) =>
    `Appointment booked${forPatient(patientName)}${doctorName ? ` with Dr. ${doctorName}` : ""}${appointmentTime ? ` at ${appointmentTime}` : ""}.`,
  appointmentCancelled: ({ patientName }) =>
    `Appointment cancelled${forPatient(patientName)}.`,
  appointmentRescheduled: ({ patientName, appointmentTime }) =>
    `Appointment rescheduled${forPatient(patientName)}${appointmentTime ? ` to ${appointmentTime}` : ""}.`,
  patientCheckedIn: ({ patientName }) =>
    `Patient checked in${forPatient(patientName)}.`,
  consultationCompleted: ({ patientName }) =>
    `Consultation completed${forPatient(patientName)}.`,
  prescriptionGenerated: ({ patientName }) =>
    `Prescription generated${forPatient(patientName)}.`,
  billingCompleted: ({ patientName, amount }) =>
    `Billing completed${forPatient(patientName)}${amount ? `. Amount received: ${amount}` : ""}.`
};

export function getHospitalWorkflowSpeechText(
  event: HospitalWorkflowEvent,
  context: HospitalWorkflowSpeechContext = {}
) {
  return workflowMessages[event](context);
}

function forPatient(patientName?: string) {
  return patientName ? ` for ${patientName}` : "";
}
