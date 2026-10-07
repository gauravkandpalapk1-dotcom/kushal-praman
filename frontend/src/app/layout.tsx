import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ServiceWorker } from "@/components/service-worker";

export const metadata: Metadata = {
  title: "Kaushal Pramaan · RPL Evidence Intelligence",
  description:
    "Links existing RPL evidence to the exact NQR Performance Criterion it supports. AI finds the evidence; the assessor decides. SIH26242 · Team AQUILA123.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#7f1414",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
        <ServiceWorker />
      </body>
    </html>
  );
}
