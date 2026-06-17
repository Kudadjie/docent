import type { Metadata } from 'next';
import './globals.css';
import ScreenSizeGate from '@/components/ScreenSizeGate';
import TabGuard from '@/components/TabGuard';
import WhatsNewToast from '@/components/WhatsNewToast';
import { NotificationProvider } from '@/lib/notifications';
import { AppRunProvider } from '@/lib/app-run-context';
import { StudioRunProvider } from '@/lib/studio-run-context';

export const metadata: Metadata = {
  title: 'Docent',
  description: 'Your grad school AI.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full" data-theme="light" suppressHydrationWarning>
      <head suppressHydrationWarning>
        {/* Theme + loading screen — runs synchronously before first paint.
            Uses a CSS class on <html> so React hydration can't remove it. */}
        {/* Runs synchronously before first paint.
            Loading overlay uses body::before — CSS pseudo-elements are
            invisible to React so nothing can remove them during hydration. */}
        <script dangerouslySetInnerHTML={{ __html:
          `(function(){try{` +
          // Resolve theme: stored preference wins, else system; light is default.
          `var t=localStorage.getItem('docent:dark');` +
          `var dk=t!==null?t==='true':window.matchMedia('(prefers-color-scheme:dark)').matches;` +
          `document.documentElement.setAttribute('data-theme',dk?'dark':'light');` +
          // Pick colours before CSS loads — warm cream / warm navy + coral spinner
          `var bg=dk?'#14171c':'#ffffff';` +
          `var ring=dk?'rgba(255,255,255,0.1)':'rgba(20,23,30,0.1)';` +
          // Inject <style> — lives in <head>, outside React's root
          `var s=document.createElement('style');` +
          `s.id='_dls';` +
          `s.textContent=` +
            `'@keyframes _dspin{from{transform:translate(-50%,-50%) rotate(0deg)}to{transform:translate(-50%,-50%) rotate(360deg)}}'` +
            `+'body::before{content:"";position:fixed;inset:0;z-index:9999;background:'+bg+';transition:opacity .35s}'` +
            `+'body::after{content:"";position:fixed;top:50%;left:50%;z-index:10000;'` +
            `+'width:22px;height:22px;border-radius:50%;border:2px solid '+ring+';border-top-color:#5db8a6;animation:_dspin .75s linear infinite;transition:opacity .35s}';` +
          `document.head.appendChild(s);` +
          // Dismiss: fade then remove the <style>
          `var start=Date.now();` +
          `function dismiss(){` +
          `s.textContent='body::before,body::after{opacity:0!important;transition:opacity .35s ease}';` +
          `setTimeout(function(){if(s.parentNode)s.parentNode.removeChild(s);},350);` +
          `}` +
          `window.addEventListener('load',function(){setTimeout(dismiss,Math.max(0,2000-(Date.now()-start)));});` +
          `setTimeout(dismiss,6000);` +
          `}catch(e){}})();`
        }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600&family=Cormorant+Garamond:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full antialiased">
        <TabGuard />
        <ScreenSizeGate />
        <AppRunProvider>
          <NotificationProvider>
            <StudioRunProvider>{children}</StudioRunProvider>
            <WhatsNewToast />
          </NotificationProvider>
        </AppRunProvider>
      </body>
    </html>
  );
}
