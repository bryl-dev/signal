import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Signal — Personal intelligence feed",
  description: "Stay informed about the topics you care about, without the noise.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
