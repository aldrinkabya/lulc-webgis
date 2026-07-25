import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "WebGIS Platform for Multi-Temporal LULC Monitoring in Bangladesh",
  description: "Interactive WebGIS platform for visualizing and analyzing multi-temporal land use and land cover (LULC) change in Bangladesh using deep learning segmentation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning={true} 
      >
        {children}
      </body>
    </html>
  );
}
