import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.API_INTERNAL_URL ||
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

export async function GET(
  _req: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const upstream = await fetch(`${API_URL}/api/v1/attachments/${id}/content`, {
    headers: cookieHeader ? { Cookie: cookieHeader } : {},
    cache: "no-store",
  });

  if (!upstream.ok) {
    return NextResponse.json({ error: "Attachment not found" }, { status: upstream.status });
  }

  const buf = await upstream.arrayBuffer();
  const contentType = upstream.headers.get("content-type") || "application/octet-stream";
  const disposition = upstream.headers.get("content-disposition") || "inline";
  return new NextResponse(buf, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": disposition,
      "Cache-Control": "private, max-age=300",
    },
  });
}
