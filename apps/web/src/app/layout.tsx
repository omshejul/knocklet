import type { Metadata } from "next";
import { Bellota_Text } from "next/font/google";
import "./globals.css";

const bellotaText = Bellota_Text({
  variable: "--font-bellota-text",
  subsets: ["latin"],
  weight: ["300", "400", "700"],
});

export const metadata: Metadata = {
  title: "LinkedIn CLI sign in",
  description: "Connect LinkedIn to the local LinkedIn CLI from your browser.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${bellotaText.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
