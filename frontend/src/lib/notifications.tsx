'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

export type NotifType = 'update' | 'info' | 'warning' | 'error';

export interface AppNotification {
  id: string;
  type: NotifType;
  title: string;
  body: string;
  timestamp: string;
  read: boolean;
}

interface NotificationContextValue {
  notifications: AppNotification[];
  unreadCount: number;
  addNotification: (n: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => void;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  clearAll: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

const STORAGE_KEY = 'docent:notifications';
const VERSION_CHECK_KEY = 'docent:lastVersionCheck';
const CHECK_INTERVAL_MS = 8 * 60 * 60 * 1000; // 8 hours

function loadNotifications(): AppNotification[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as AppNotification[];
  } catch {
    return [];
  }
}

function saveNotifications(notifs: AppNotification[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notifs.slice(0, 50)));
  } catch {}
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const checkedRef = useRef(false);

  useEffect(() => {
    queueMicrotask(() => {
      setNotifications(loadNotifications());
    });
  }, []);

  const addNotification = useCallback((n: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => {
    const notif: AppNotification = {
      ...n,
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
      read: false,
    };
    setNotifications(prev => {
      const next = [notif, ...prev].slice(0, 50);
      saveNotifications(next);
      return next;
    });
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications(prev => {
      const next = prev.map(n => ({ ...n, read: true }));
      saveNotifications(next);
      return next;
    });
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications(prev => {
      const next = prev.filter(n => n.id !== id);
      saveNotifications(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
    saveNotifications([]);
  }, []);

  // Auto-check on first app open per 8h window
  useEffect(() => {
    if (checkedRef.current) return;
    checkedRef.current = true;

    try {
      const last = localStorage.getItem(VERSION_CHECK_KEY);
      const now = Date.now();
      if (last && now - parseInt(last, 10) < CHECK_INTERVAL_MS) return;
    } catch {}

    fetch('/api/version')
      .then(r => r.json())
      .then((data: { installed: string | null; latest: string | null; up_to_date: boolean | null }) => {
        try { localStorage.setItem(VERSION_CHECK_KEY, Date.now().toString()); } catch {}
        if (data.up_to_date === false && data.latest) {
          addNotification({
            type: 'update',
            title: 'Docent update available',
            body: `v${data.latest} is out (you have v${data.installed ?? '?'}). Run \`pip install -U docent-cli\` to update.`,
          });
        }
      })
      .catch(() => {});
  }, [addNotification]);

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <NotificationContext.Provider value={{ notifications, unreadCount, addNotification, markAllRead, dismiss, clearAll }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used within NotificationProvider');
  return ctx;
}
