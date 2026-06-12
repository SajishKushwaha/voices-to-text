export type RecorderStatus =
  | "idle"
  | "requesting-permission"
  | "recording"
  | "paused"
  | "stopped"
  | "error";

export type ChatMessageStatus = "ready" | "transcribing" | "error";

export interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
}

export interface TranscriptionResponse {
  success: true;
  text: string;
  language: string;
  detectedLanguage?: string;
  languageFallbackUsed?: boolean;
  processingTime: number;
  duration?: number;
  segments?: TranscriptionSegment[];
}

export interface ApiErrorResponse {
  success: false;
  error: string;
  code: string;
}

export interface VoiceChatMessage {
  id: string;
  audioUrl: string;
  createdAt: string;
  durationSeconds: number;
  status: ChatMessageStatus;
  audioBlob: Blob;
  text?: string;
  language?: string;
  detectedLanguage?: string;
  languageFallbackUsed?: boolean;
  processingTime?: number;
  error?: string;
}
