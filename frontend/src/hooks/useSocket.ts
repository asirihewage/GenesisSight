import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";
import type { WsMessage } from "@/types";

/**
 * Reconnecting WebSocket hook. Returns the latest message plus connection state.
 * Reconnects automatically with backoff; pings the server to keep it alive.
 */
export function useSocket(): { message: WsMessage | null; connected: boolean; onEvent: (cb: (msg: WsMessage) => void) => () => void } {
  const [message, setMessage] = useState<WsMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const callbacksRef = useRef<Set<(msg: WsMessage) => void>>(new Set());

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      retryRef.current = 0;
      setConnected(true);
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WsMessage;
        setMessage(data);
        callbacksRef.current.forEach((cb) => cb(data));
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      setConnected(false);
      const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
      retryRef.current += 1;
      timerRef.current = window.setTimeout(connect, delay);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const onEvent = useCallback((cb: (msg: WsMessage) => void) => {
    callbacksRef.current.add(cb);
    return () => callbacksRef.current.delete(cb);
  }, []);

  return { message, connected, onEvent };
}
