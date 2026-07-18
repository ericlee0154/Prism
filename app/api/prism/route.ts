import { NextResponse } from "next/server";
import { bootstrap, identityFromRequest, mutate } from "../../../lib/prism-store";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const identity = await identityFromRequest(request);
    return NextResponse.json(await bootstrap(identity), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Prism storage is temporarily unavailable.",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 503 },
    );
  }
}
export async function POST(request: Request) {
  try {
    const identity = await identityFromRequest(request);
    if (!identity) {
      return NextResponse.json(
        { error: "Sign in to save research records.", signInPath: "/signin-with-chatgpt?return_to=%2F" },
        { status: 401 },
      );
    }
    const input = await request.json() as Record<string, unknown>;
    return NextResponse.json({ data: await mutate(identity, input) });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    const expected = /Invalid|Unknown|must be/.test(message);
    return NextResponse.json(
      { error: expected ? message : "The operation could not be completed." },
      { status: expected ? 400 : 500 },
    );
  }
}
