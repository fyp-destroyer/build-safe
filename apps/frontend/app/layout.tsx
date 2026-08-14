import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "@/lib/theme";
import { ConvexClientProvider } from "@/components/ConvexClientProvider";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CanIDIY",
  description: "Decide whether a DIY task is safe to attempt.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col">
        <div
          dangerouslySetInnerHTML={{
            __html: `<!--
DIRECTION CONTRACT — homepage (/) · seed adb6da48 · surface/persuade

THESIS: CanIDIY's front door is the product's own case register, not a pitch about it.
  It refuses the category default (hero headline, three feature cards, a testimonial) and
  proves the mechanism by filing three real assessments instead of describing one.
OWN-WORLD: near-black #060606 ground ruled by 1px hairlines; safety-orange as the
  register's active ink (rule ids, the max operator, actions); Inter throughout with
  monospace reserved for reference data — ids, floors, counts, levels. The five risk
  colours appear only inside verdict chips and stamps, never as chrome.
STORY: a homeowner mid-problem learns the product answers WHETHER, not how; sees it
  overrule its own classifier three times; understands that unsure escalates; starts one.
FIRST VIEWPORT: left-set headline at up to 5.25rem over one paragraph and two actions,
  then the five-verdict key as a ruled table carrying the real per-level rule counts.
  Primary action sits directly under the paragraph and again in the sticky header.
FORM: case-file register — candidate 6 of the grounded structural list; assigned by seed adb6da48.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`,
          }}
        />
        {/* Auth outside theme: Clerk's session must be established before any
            component that reads it renders, and ThemeProvider is purely visual. */}
        <ConvexClientProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </ConvexClientProvider>
      </body>
    </html>
  );
}
