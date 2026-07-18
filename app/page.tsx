import { PrismApp } from "./prism-app";
import { getChatGPTUser } from "./chatgpt-auth";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function Home() {
  const authenticatedUser = await getChatGPTUser();
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "";
  const local = host.startsWith("localhost") || host.startsWith("127.0.0.1");
  const user = authenticatedUser
    ? { displayName: authenticatedUser.displayName, email: authenticatedUser.email, local: false }
    : local
      ? { displayName: "Local researcher", email: "local@prism.dev", local: true }
      : null;

  return <PrismApp initialUser={user} />;
}
