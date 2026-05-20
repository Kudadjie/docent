import type { Metadata } from 'next';
import './globals.css';
import ScreenSizeGate from '@/components/ScreenSizeGate';
import TabGuard from '@/components/TabGuard';
import { NotificationProvider } from '@/lib/notifications';

export const metadata: Metadata = {
  title: 'Docent',
  description: 'Your grad school AI.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* Runs synchronously before first paint — eliminates theme flash */}
        <script dangerouslySetInnerHTML={{ __html:
          `(function(){try{var t=localStorage.getItem('docent:dark');` +
          `document.documentElement.setAttribute('data-theme',(t===null||t==='true')?'dark':'light');}catch(e){}})();`
        }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full antialiased">
        <TabGuard />
        <ScreenSizeGate />
        <NotificationProvider>{children}</NotificationProvider>
      </body>
    </html>
  );
}
