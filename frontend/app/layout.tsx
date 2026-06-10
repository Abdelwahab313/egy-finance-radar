import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EGY Finance — EGX Intelligence",
  description: "EGX stock classification & paper portfolio (10,000 EGP)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
