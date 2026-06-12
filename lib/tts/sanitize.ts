const DEFAULT_MAX_TEXT_LENGTH = 700;

export class TtsInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TtsInputError";
  }
}

export function getMaxTtsTextLength() {
  const configured = Number(process.env.TTS_MAX_TEXT_LENGTH);
  return Number.isFinite(configured) && configured > 0
    ? Math.min(configured, 2000)
    : DEFAULT_MAX_TEXT_LENGTH;
}

export function sanitizeTtsText(input: unknown): string {
  if (typeof input !== "string") {
    throw new TtsInputError("Text must be a string.");
  }

  const sanitized = input
    .normalize("NFKC")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!sanitized) {
    throw new TtsInputError("Text cannot be empty.");
  }

  const maxLength = getMaxTtsTextLength();

  if (sanitized.length > maxLength) {
    throw new TtsInputError(`Text must be ${maxLength} characters or fewer.`);
  }

  return sanitized;
}
