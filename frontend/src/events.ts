// Server-sent build events (/api/builds/events) fanned out to page listeners.

import type { BuildEvent } from "./api";

type Listener = (event: BuildEvent) => void;

const listeners = new Set<Listener>();
const statusListeners = new Set<(online: boolean) => void>();
let source: EventSource | null = null;

export function connectEvents(): void {
  if (source) return;
  source = new EventSource("/api/builds/events");
  source.onopen = () => statusListeners.forEach((fn) => fn(true));
  source.onerror = () => statusListeners.forEach((fn) => fn(false));
  source.onmessage = (msg) => {
    let event: BuildEvent;
    try {
      event = JSON.parse(msg.data) as BuildEvent;
    } catch {
      return;
    }
    listeners.forEach((fn) => fn(event));
  };
}

export function onBuildEvent(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function onConnection(fn: (online: boolean) => void): void {
  statusListeners.add(fn);
}
