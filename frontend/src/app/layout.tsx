import type { Metadata } from 'next';
import './globals.css';
import ScreenSizeGate from '@/components/ScreenSizeGate';
import { NotificationProvider } from '@/lib/notifications';

export const metadata: Metadata = {
  title: 'Docent',
  description: 'Your grad school AI.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <head>
        {/* Runs synchronously before first paint — prevents dark-mode flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{if(localStorage.getItem('docent:dark')==='true'){document.documentElement.setAttribute('data-theme','dark');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="h-full antialiased">
        <ScreenSizeGate />
        <NotificationProvider>{children}</NotificationProvider>
      </body>
    </html>
  );
}
