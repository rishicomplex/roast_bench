// Private host for the RoastBench rating app.
// Jobs: gate everything behind a Google-allowlist sign-in (same pattern as the
// `korean` Worker), serve the repo's static assets (HTML pages + jokes/models/
// personalities JSON), and persist rankings in Workers KV so rating works from
// anywhere. The repo stays the source of truth for the public showcase — pull
// KV back into data/rankings.json with scripts/pull_rankings.sh.

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64urlEncode(bytes) {
  const arr = new Uint8Array(bytes);
  let s = "";
  for (let i = 0; i < arr.length; i++) s += String.fromCharCode(arr[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64urlToBytes(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/");
  while (str.length % 4) str += "=";
  const bin = atob(str);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
async function hmacKey(secret) {
  return crypto.subtle.importKey("raw", enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
async function signToken(payload, secret) {
  const header = b64urlEncode(enc.encode(JSON.stringify({ alg: "HS256", typ: "JWT" })));
  const body = b64urlEncode(enc.encode(JSON.stringify(payload)));
  const data = `${header}.${body}`;
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(secret), enc.encode(data));
  return `${data}.${b64urlEncode(sig)}`;
}
async function verifyToken(token, secret) {
  const parts = (token || "").split(".");
  if (parts.length !== 3) return null;
  const data = `${parts[0]}.${parts[1]}`;
  const ok = await crypto.subtle.verify("HMAC", await hmacKey(secret),
    b64urlToBytes(parts[2]), enc.encode(data));
  if (!ok) return null;
  let payload;
  try { payload = JSON.parse(dec.decode(b64urlToBytes(parts[1]))); } catch { return null; }
  if (payload.exp && Math.floor(Date.now() / 1000) > payload.exp) return null;
  return payload;
}
async function verifyGoogleToken(idToken, clientId) {
  const res = await fetch("https://oauth2.googleapis.com/tokeninfo?id_token=" + encodeURIComponent(idToken));
  if (!res.ok) return null;
  const data = await res.json();
  if (data.aud !== clientId) return null;
  if (data.iss !== "accounts.google.com" && data.iss !== "https://accounts.google.com") return null;
  if (data.email_verified !== true && data.email_verified !== "true") return null;
  return data;
}

function getCookie(request, name) {
  const c = request.headers.get("Cookie") || "";
  const m = c.match(new RegExp("(?:^|; )" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[1]) : null;
}
function isAllowed(email, env) {
  const allowed = (env.ALLOWED_EMAILS || "").split(",").map(e => e.trim().toLowerCase()).filter(Boolean);
  return allowed.includes((email || "").toLowerCase());
}
function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status, headers: { "Content-Type": "application/json", ...headers },
  });
}

const LOGIN_PAGE = (clientId) => `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RoastBench</title></head>
<body style="margin:0;min-height:100dvh;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:18px;font-family:system-ui;background:#111;color:#eee">
<div style="font-size:48px">🔥</div><div style="opacity:.5">Sign in to rate roasts</div><div id="g"></div>
<script src="https://accounts.google.com/gsi/client" async></script>
<script>
window.onload=function(){google.accounts.id.initialize({client_id:"${clientId}",callback:async function(r){
 const res=await fetch("/api/auth",{method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({googleToken:r.credential})});
 if(res.ok){location.reload()}else{const e=await res.json();alert(e.error||"sign-in failed")}}});
 google.accounts.id.renderButton(document.getElementById("g"),{theme:"filled_black",size:"large"});};
</script></body></html>`;

// Rankings live in KV under one key, same shape as data/rankings.json:
// {"rankings": {pid: [model_id,…]}, "lol_flags": {pid: [model_id,…]}}.
// If KV is empty (fresh deploy), fall back to the committed file so the app
// starts from the repo's current state.
async function loadRankings(env, request) {
  const kv = await env.RANKINGS.get("rankings", "json");
  if (kv) return kv;
  const url = new URL(request.url);
  url.pathname = "/data/rankings.json";
  const res = await env.ASSETS.fetch(new Request(url));
  if (res.ok) return res.json();
  return { rankings: {}, lol_flags: {} };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Sign-in: verify Google token, set a long-lived HttpOnly cookie.
    if (url.pathname === "/api/auth" && request.method === "POST") {
      if (!env.TOKEN_SECRET) return json({ error: "TOKEN_SECRET not set" }, 500);
      let body; try { body = await request.json(); } catch { return json({ error: "bad request" }, 400); }
      const info = await verifyGoogleToken(body.googleToken, env.GOOGLE_CLIENT_ID);
      if (!info) return json({ error: "invalid google token" }, 401);
      const email = (info.email || "").toLowerCase();
      if (!isAllowed(email, env)) return json({ error: "not on the list" }, 403);
      const exp = Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 365;
      const token = await signToken({ email, exp }, env.TOKEN_SECRET);
      return json({ ok: true }, 200, {
        "Set-Cookie": `roast_session=${encodeURIComponent(token)}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=31536000`,
      });
    }

    if (url.pathname === "/api/logout") {
      return new Response(null, {
        status: 302,
        headers: { "Location": "/", "Set-Cookie": "roast_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0" },
      });
    }

    // Gate everything else behind a valid session cookie.
    const payload = await verifyToken(getCookie(request, "roast_session"), env.TOKEN_SECRET);
    if (!payload || !isAllowed(payload.email, env)) {
      return new Response(LOGIN_PAGE(env.GOOGLE_CLIENT_ID), {
        status: 200, headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // Authenticated → current rankings (KV, falling back to the committed file).
    if (url.pathname === "/api/rankings" && request.method === "GET") {
      return json(await loadRankings(env, request));
    }

    // Authenticated → save the ranking for one personality.
    // Body: {"order": [model_id,…], "lol": [model_id,…]}
    const rankMatch = url.pathname.match(/^\/api\/rankings\/([\w.-]+)$/);
    if (rankMatch && request.method === "POST") {
      let body; try { body = await request.json(); } catch { return json({ error: "bad request" }, 400); }
      const order = Array.isArray(body.order) ? body.order.filter(m => typeof m === "string") : null;
      const lol = Array.isArray(body.lol) ? body.lol.filter(m => typeof m === "string") : [];
      if (!order) return json({ error: "order must be a list of model ids" }, 400);
      const rankings = await loadRankings(env, request);
      rankings.rankings[rankMatch[1]] = order;
      rankings.lol_flags[rankMatch[1]] = lol;
      await env.RANKINGS.put("rankings", JSON.stringify(rankings));
      return json({ ok: true });
    }

    // Authenticated → static assets (HTML pages, style.css, the JSON data).
    return env.ASSETS.fetch(request);
  },
};
