import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local Voice AI",
  description:
    "Self-hosted voice recording, transcription, and speech tools using local models."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
