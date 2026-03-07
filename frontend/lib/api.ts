const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("lexgraph_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ─── Auth ──────────────────────────────────────────────────────────────────────

export async function login(username: string, password: string) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json() as Promise<{ access_token: string; refresh_token: string; token_type: string }>;
}

export async function refreshToken(refreshTok: string) {
  const res = await fetch(`${BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshTok }),
  });
  if (!res.ok) throw new Error("Session expired");
  return res.json() as Promise<{ access_token: string; refresh_token: string; token_type: string }>;
}

export async function getMe() {
  const res = await fetch(`${BASE_URL}/auth/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json() as Promise<{ username: string; full_name: string; role: string }>;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export async function* streamChat(
  query: string,
  jurisdiction: string,
  sessionId: string,
  history: { role: string; content: string }[]
): AsyncGenerator<{ token?: string; done?: boolean; citations?: unknown[] }> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ query, jurisdiction, session_id: sessionId, history }),
  });

  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6));
        } catch {
          // ignore malformed SSE lines
        }
      }
    }
  }
}

// ─── Upload ───────────────────────────────────────────────────────────────────

export async function uploadDocument(file: File, documentType: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  const res = await fetch(`${BASE_URL}/upload`, { method: "POST", headers: authHeaders(), body: formData });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function ingestDocument(docId: string) {
  const res = await fetch(`${BASE_URL}/ingest/${docId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);
  return res.json() as Promise<{ doc_id: string; vectors_indexed: number }>;
}

// ─── DD Agent ─────────────────────────────────────────────────────────────────

export async function startDDAgent(payload: {
  prompt: string;
  jurisdiction: string;
  document_ids: string[];
  transaction_type: string;
}) {
  const res = await fetch(`${BASE_URL}/agent/dd`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`DD Agent start failed: ${res.status}`);
  return res.json() as Promise<{ task_id: string; status: string; estimated_seconds: number }>;
}

export async function getDDAgentStatus(taskId: string) {
  const res = await fetch(`${BASE_URL}/agent/dd/${taskId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`DD Agent poll failed: ${res.status}`);
  return res.json();
}

export async function submitDDReview(taskId: string, notes: string, approved: boolean) {
  const res = await fetch(`${BASE_URL}/agent/dd/${taskId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ notes, approved }),
  });
  if (!res.ok) throw new Error(`DD review submission failed: ${res.status}`);
  return res.json();
}

// ─── Contract Review Agent ────────────────────────────────────────────────────

export async function startContractReview(payload: {
  document_id: string;
  jurisdiction: string;
  contract_type: string;
  client_position: string;
}) {
  const res = await fetch(`${BASE_URL}/agent/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Contract review start failed: ${res.status}`);
  return res.json();
}

export async function getContractReviewStatus(taskId: string) {
  const res = await fetch(`${BASE_URL}/agent/review/${taskId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Contract review poll failed: ${res.status}`);
  return res.json();
}

// ─── Tasks ────────────────────────────────────────────────────────────────────

export async function listDDTasks() {
  const res = await fetch(`${BASE_URL}/agent/dd`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List DD tasks failed: ${res.status}`);
  return res.json() as Promise<unknown[]>;
}

export async function listReviewTasks() {
  const res = await fetch(`${BASE_URL}/agent/review`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`List review tasks failed: ${res.status}`);
  return res.json() as Promise<unknown[]>;
}

async function _downloadBlob(url: string, filename: string): Promise<void> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = `Export failed: ${res.status}`;
    try { detail = JSON.parse(text)?.detail ?? detail; } catch { /* use status */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(objectUrl), 200);
}

export function downloadDDReport(taskId: string): void {
  _downloadBlob(`${BASE_URL}/agent/dd/${taskId}/export`, `dd_report_${taskId.slice(0, 8)}.pdf`)
    .catch((e) => alert(`PDF export failed: ${e.message}`));
}

export function downloadRedlinedDocx(taskId: string): void {
  _downloadBlob(`${BASE_URL}/agent/review/${taskId}/export`, `redlined_${taskId.slice(0, 8)}.docx`)
    .catch((e) => alert(`DOCX export failed: ${e.message}`));
}

// ─── Graph ────────────────────────────────────────────────────────────────────

export async function searchGraph(query: string, jurisdiction: string) {
  const params = new URLSearchParams({ q: query, jurisdiction });
  const res = await fetch(`${BASE_URL}/graph/search?${params}`);
  if (!res.ok) throw new Error(`Graph search failed: ${res.status}`);
  return res.json();
}
