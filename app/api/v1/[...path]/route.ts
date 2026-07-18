import { NextRequest } from "next/server";

const LOCAL_API_ORIGIN = "http://127.0.0.1:8000";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const incomingUrl = new URL(request.url);
  const targetUrl = new URL(`/api/v1/${path.join("/")}`, LOCAL_API_ORIGIN);
  targetUrl.search = incomingUrl.search;

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
      },
      body:
        request.method === "GET" || request.method === "HEAD"
          ? undefined
          : await request.text(),
      cache: "no-store",
    });
    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "content-type":
          response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    return Response.json(
      {
        detail:
          error instanceof Error
            ? `Local Prism API unavailable: ${error.message}`
            : "Local Prism API unavailable",
      },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
