"use client";

import { AlertCircle, Mic } from "lucide-react";

interface PermissionNoticeProps {
  permissionState: PermissionState | "unsupported" | "unknown";
  error?: string | null;
}

export function PermissionNotice({
  error,
  permissionState
}: PermissionNoticeProps) {
  if (permissionState === "granted" && !error) {
    return null;
  }

  const isBlocked = permissionState === "denied" || permissionState === "unsupported";

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div className="flex gap-3">
        {isBlocked ? (
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        ) : (
          <Mic className="mt-0.5 h-4 w-4 shrink-0" />
        )}
        <p>
          {error ??
            "Microphone access is required before recording voice messages."}
        </p>
      </div>
    </div>
  );
}
