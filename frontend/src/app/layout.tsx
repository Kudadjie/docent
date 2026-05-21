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
        {/* Theme + loading screen — runs synchronously before first paint */}
        <script dangerouslySetInnerHTML={{ __html:
          `(function(){` +
          `try{` +
          // Apply stored theme preference
          `var t=localStorage.getItem('docent:dark');` +
          `if(t!==null)document.documentElement.setAttribute('data-theme',t==='true'?'dark':'light');` +
          // Determine colours
          `var dark=t!==null?t==='true':window.matchMedia('(prefers-color-scheme:dark)').matches;` +
          `var bg=dark?'#0d0d0d':'#f8f9fa';` +
          `var ring=dark?'rgba(255,255,255,0.08)':'rgba(0,0,0,0.08)';` +
          // Spinner keyframe
          `var s=document.createElement('style');` +
          `s.textContent='@keyframes _dspin{to{transform:rotate(360deg)}}';` +
          `document.head.appendChild(s);` +
          // Overlay div
          `var el=document.createElement('div');` +
          `el.style.cssText='position:fixed;inset:0;z-index:9999;background:'+bg+';display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px';` +
          // Logo
          `var img=document.createElement('img');` +
          `img.src=dark?'/logo-dark.svg':'/logo-light.svg';` +
          `img.style.cssText='width:36px;height:36px';` +
          `el.appendChild(img);` +
          // Spinner
          `var sp=document.createElement('div');` +
          `sp.style.cssText='width:18px;height:18px;border-radius:50%;border:2px solid '+ring+';border-top-color:#18E299;animation:_dspin 0.75s linear infinite';` +
          `el.appendChild(sp);` +
          `document.documentElement.appendChild(el);` +
          // Dismiss: wait for window.load AND 2 seconds minimum
          `var start=Date.now();` +
          `function dismiss(){` +
          `if(!el.parentNode)return;` +
          `el.style.transition='opacity 0.35s ease';` +
          `el.style.opacity='0';` +
          `setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},350);` +
          `}` +
          `window.addEventListener('load',function(){` +
          `setTimeout(dismiss,Math.max(0,2000-(Date.now()-start)));` +
          `});` +
          // Hard fallback: never block longer than 6s
          `setTimeout(dismiss,6000);` +
          `}catch(e){}` +
          `})();`
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
