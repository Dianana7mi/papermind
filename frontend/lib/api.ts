export type Library = { id: string; name: string; description: string };
export type Paper = {
  id: string;
  title: string;
  filename: string;
  status: string;
  error?: string;
  metadata?: Record<string, unknown>;
};
export type Experiment = {
  id: string;
  paper_id: string;
  record: Record<string, unknown> & {
    provenance: {
      evidence_ids: string[];
      page_number: number | null;
      table_id: string | null;
      original_text: string | null;
    };
  };
  version: number;
};
export type Citation = {
  id: string;
  paper_id: string;
  page: number | null;
  text: string;
  url?: string;
};
export type ResearchAnswer = {
  answer: string;
  conversation_id: string;
  citations: Citation[];
  trace: { node: string; elapsed_ms: number }[];
  verification: unknown[];
  errors: string[];
  usage: {
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number | null;
  };
  task_type: string;
  comparisons: unknown[];
};

export async function api<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error?.message || `HTTP ${response.status}`);
  }
  const ensureSession = () => {
    if (
      token &&
      typeof window !== "undefined" &&
      sessionStorage.getItem("papermind_token") !== token
    )
      throw new Error("Session changed; response discarded");
  };
  ensureSession();
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  ensureSession();
  return data;
}

export async function streamResearch(
  token: string,
  body: unknown,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal: AbortSignal,
) {
  const response = await fetch("/api/v1/research/chat/stream", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Research failed");
  }
  if (!response.body) throw new Error("Streaming unavailable");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const event = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const type = event.match(/^event: (.+)$/m)?.[1];
      const data = event.match(/^data: (.+)$/m)?.[1];
      if (type && data) onEvent(type, JSON.parse(data));
    }
    if (done) break;
  }
}
