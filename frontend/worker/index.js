export default {
  async fetch(request, env) {
    const incomingUrl = new URL(request.url);

    if (incomingUrl.pathname.startsWith("/api/")) {
      const backendUrl = String(env.BACKEND_URL || "").replace(/\/$/, "");

      if (!backendUrl) {
        return new Response(
          JSON.stringify({ detail: "BACKEND_URL non configurato" }),
          {
            status: 500,
            headers: { "content-type": "application/json; charset=utf-8" },
          }
        );
      }

      const apiPath = incomingUrl.pathname.replace(/^\/api/, "") || "/";
      const targetUrl = new URL(`${apiPath}${incomingUrl.search}`, backendUrl);
      const headers = new Headers(request.headers);
      headers.delete("host");

      const init = {
        method: request.method,
        headers,
        redirect: "follow",
      };

      if (request.method !== "GET" && request.method !== "HEAD") {
        init.body = request.body;
      }

      const upstream = await fetch(targetUrl.toString(), init);
      const responseHeaders = new Headers(upstream.headers);
      responseHeaders.set("cache-control", "no-store");

      return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: responseHeaders,
      });
    }

    return env.ASSETS.fetch(request);
  },
};
