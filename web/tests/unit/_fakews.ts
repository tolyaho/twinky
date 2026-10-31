// A scriptable WebSocket stand-in for deterministic tests (no network). Mirrors the slice of the
// browser WebSocket API that TwitchChatClient uses.
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static reset() {
    FakeWebSocket.instances = [];
  }
  static last(): FakeWebSocket {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  url: string;
  readyState = 0;
  sent: string[] = [];
  onopen: unknown = null;
  onmessage: unknown = null;
  onclose: unknown = null;
  onerror: unknown = null;
  private listeners: Record<string, ((ev: unknown) => void)[]> = {
    open: [],
    message: [],
    close: [],
    error: [],
  };

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, fn: (ev: unknown) => void) {
    (this.listeners[type] ??= []).push(fn);
  }
  removeEventListener(type: string, fn: (ev: unknown) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== fn);
  }
  send(s: string) {
    this.sent.push(s);
  }
  close() {
    this.readyState = 3;
  }

  private emit(type: string, ev: unknown) {
    for (const fn of [...(this.listeners[type] ?? [])]) fn(ev);
  }

  // --- test drivers ---
  fireOpen() {
    this.readyState = 1;
    this.emit("open", {});
  }
  fireMessage(data: string) {
    this.emit("message", { data });
  }
  fireClose(code = 1006) {
    this.readyState = 3;
    this.emit("close", { code });
  }
  fireError() {
    this.emit("error", {});
  }
}

let seq = 0;
/** Build a well-formed tagged PRIVMSG line with a unique id and given text. */
export function privmsgLine(
  text: string,
  opts: { id?: string; ts?: number; name?: string; channel?: string } = {},
): string {
  const id = opts.id ?? `id${++seq}`;
  const ts = opts.ts ?? 1_700_000_000_000 + seq * 100;
  const name = opts.name ?? `User${seq}`;
  const channel = opts.channel ?? "xqc";
  return (
    `@badge-info=;badges=;display-name=${name};id=${id};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${name.toLowerCase()}!${name.toLowerCase()}@${name.toLowerCase()}.tmi.twitch.tv ` +
    `PRIVMSG #${channel} :${text}`
  );
}
