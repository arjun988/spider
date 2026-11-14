import type { Metadata } from "next";
import { JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Spider — AI Code Review",
  description: "Internal AI-powered GitHub code review platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('spider-theme');var d=window.matchMedia('(prefers-color-scheme: dark)').matches;var m=t==='light'||t==='dark'?t:(d?'dark':'light');var r=document.documentElement;r.classList.toggle('dark',m==='dark');r.style.colorScheme=m;}catch(e){}})();`,
          }}
        />
      </head>
      <body className={`${jakarta.variable} ${jetbrains.variable} font-sans antialiased`}>
        <ThemeProvider>
          <QueryProvider>{children}</QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
