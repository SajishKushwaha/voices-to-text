export type TtsVoiceId =
  | "en_US-lessac-medium"
  | "hi_IN-pratham-medium"
  | "hi_IN-priyamvada-medium";

export type TtsLanguage = "en-US" | "hi-IN";

export interface TtsVoice {
  id: TtsVoiceId;
  label: string;
  language: TtsLanguage;
  modelFile: string;
  configFile: string;
  modelUrl: string;
  configUrl: string;
}

export interface TtsRequestBody {
  text: string;
  voiceId?: TtsVoiceId;
}

export interface TtsApiResponse {
  audioUrl: string;
  cacheKey: string;
  voiceId: TtsVoiceId;
  textLength: number;
  cached: boolean;
  expiresInSeconds: number;
}

export interface TtsErrorResponse {
  error: string;
  code: string;
}
