import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin", "vietnamese"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "HDSD Multimodal Chatbot - Hướng Dẫn Sử Dụng",
  description: "Trợ lý AI Đa phương tiện Hướng dẫn Sử dụng Phần mềm",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={montserrat.className}>
      <body className="antialiased bg-slate-100 text-slate-800 min-h-screen text-[15px]">
        {children}
      </body>
    </html>
  );
}
