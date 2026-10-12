import { NextResponse } from "next/server";

const PREFERRED = [
  "gemini-flash-latest",
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "gemini-flash-lite-latest",
  "gemini-pro-latest",
  "gemini-2.5-pro",
];

const SKIP_MARKERS = ["image", "tts", "live", "embedding", "aqa", "vision", "audio"];

function rankModel(model: string): number {
  const m = model.toLowerCase();
  if (m.endsWith("flash-latest")) return 0;
  if (m.includes("2.5-flash") && !m.includes("lite")) return 1;
  if (m.includes("flash-lite")) return 2;
  if (m.includes("2.5-pro") || m.endsWith("pro-latest")) return 3;
  if (m.includes("flash")) return 4;
  if (m.includes("pro")) return 5;
  return 10;
}

function buildCandidates(listed: string[]): string[] {
  const available = listed.filter(
    (name) =>
      name.startsWith("gemini-") &&
      !SKIP_MARKERS.some((marker) => name.toLowerCase().includes(marker)),
  );
  const ordered: string[] = [];
  const seen = new Set<string>();
  const add = (model: string) => {
    if (!model || seen.has(model)) return;
    seen.add(model);
    ordered.push(model);
  };
  for (const model of PREFERRED) {
    if (available.includes(model)) add(model);
  }
  for (const model of [...available].sort((a, b) => rankModel(a) - rankModel(b))) {
    add(model);
  }
  for (const model of PREFERRED) add(model);
  return ordered;
}

async function listModels(apiKey: string): Promise<string[]> {
  const listResp = await fetch("https://generativelanguage.googleapis.com/v1beta/models", {
    headers: { "x-goog-api-key": apiKey },
    cache: "no-store",
  });
  if (!listResp.ok) return [];
  const data = (await listResp.json()) as {
    models?: Array<{ name?: string; supportedGenerationMethods?: string[] }>;
  };
  return (data.models || [])
    .filter((m) => (m.supportedGenerationMethods || []).includes("generateContent"))
    .map((m) => (m.name || "").replace(/^models\//, ""))
    .filter((name) => name.startsWith("gemini-"))
    .filter((name) => !SKIP_MARKERS.some((marker) => name.toLowerCase().includes(marker)))
    .sort((a, b) => rankModel(a) - rankModel(b));
}

async function tryModel(apiKey: string, model: string): Promise<boolean> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "x-goog-api-key": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      contents: [{ parts: [{ text: "ping" }] }],
    }),
    cache: "no-store",
  });
  return resp.ok;
}

export async function POST(request: Request) {
  let apiKey = "";
  try {
    const body = (await request.json()) as { api_key?: string };
    apiKey = (body.api_key || "").trim();
  } catch {
    return NextResponse.json(
      { error: { message: "Invalid request body." } },
      { status: 400 },
    );
  }

  if (apiKey.length < 10) {
    return NextResponse.json(
      { error: { message: "API key looks too short." } },
      { status: 400 },
    );
  }

  const listed = await listModels(apiKey);
  const candidates = buildCandidates(listed);

  for (const model of candidates) {
    if (await tryModel(apiKey, model)) {
      return NextResponse.json({
        ok: true,
        verified_model: model,
        models_listed: listed.length,
        available_models: listed,
      });
    }
  }

  return NextResponse.json(
    {
      error: {
        message: `No working Gemini model found${listed.length ? ` (${listed.length} listed).` : "."}${
          listed.length ? ` Available: ${listed.slice(0, 8).join(", ")}.` : ""
        }`,
      },
    },
    { status: 400 },
  );
}
