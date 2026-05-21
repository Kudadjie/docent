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
        {/* Theme + loading screen — runs synchronously before first paint.
            Uses a CSS class on <html> so React hydration can't remove it. */}
        {/* Runs synchronously before first paint.
            Loading overlay uses body::before — CSS pseudo-elements are
            invisible to React so nothing can remove them during hydration. */}
        <script dangerouslySetInnerHTML={{ __html:
          `(function(){try{` +
          // Apply stored theme
          `var t=localStorage.getItem('docent:dark');` +
          `if(t!==null)document.documentElement.setAttribute('data-theme',t==='true'?'dark':'light');` +
          // Pick colours before CSS loads
          `var dk=t!==null?t==='true':window.matchMedia('(prefers-color-scheme:dark)').matches;` +
          `var bg=dk?'#0d0d0d':'#f8f9fa';` +
          `var ring=dk?'rgba(255,255,255,0.1)':'rgba(0,0,0,0.1)';` +
          // Inject <style> — lives in <head>, outside React's root
          `var s=document.createElement('style');` +
          `s.id='_dls';` +
          `s.textContent=` +
            `'@keyframes _dspin{from{transform:translate(-50%,-50%) rotate(0deg)}to{transform:translate(-50%,-50%) rotate(360deg)}}'` +
            `+'body::before{content:"";position:fixed;inset:0;z-index:9999;background:'+bg+';transition:opacity .35s}'` +
            `+'body::after{content:"";position:fixed;top:50%;left:50%;z-index:10000;'` +
            `+'width:22px;height:22px;border-radius:50%;border:2px solid '+ring+';border-top-color:#18E299;animation:_dspin .75s linear infinite;transition:opacity .35s}';` +
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
