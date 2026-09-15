export async function onRequest(context) {
  const backendUrl = String(context.env.BACKEND_URL || "").replace(/\/$/, "");

  if (!backendUrl) {
    return new Response(
      JSON.stringify({ detail: "BACKEND_URL non configurato" }),
      {
        status: 500,
        headers: { "content-type": "application/json; charset=utf-8" },
      }
    );
  }

  const parts = Array.isArray(context.params.path)
    ? context.params.path
    : [context.params.path].filter(Boolean);
  const incomingUrl = new URL(context.request.url);
  const targetUrl = new URL(`/${parts.join("/")}${incomingUrl.search}`, backendUrl);

  const headers = new Headers();
  const accept = context.request.headers.get("accept");
  if (accept) headers.set("accept", accept);

  const upstream = await fetch(targetUrl.toString(), {
    method: context.request.method,
    headers,
    redirect: "follow",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set("cache-control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
