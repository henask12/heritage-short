import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Red Through the Years | The Heritage Short",
  description:
    "A 90-second AI-assisted short film about Manchester United loyalty as family heritage — from childhood in Addis Ababa to the present day. Watch in English or Amharic.",
  openGraph: {
    title: "Red Through the Years",
    description:
      "Manchester United loyalty as heritage. A short film from Addis Ababa to now.",
    images: ["/stills/hero.jpg"],
    type: "website",
  },
};

const RootLayout = ({ children }: Readonly<{ children: React.ReactNode }>) => {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
};

export default RootLayout;
