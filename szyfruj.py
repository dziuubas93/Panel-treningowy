#!/usr/bin/env python3
"""Szyfruje dashboard.html hasłem -> strona logowania, która odszyfrowuje go w przeglądarce.

Użycie: DASHBOARD_PASSWORD=... python3 szyfruj.py dashboard.html public/index.html
AES-256-GCM, klucz z PBKDF2-SHA256. Sól jest stała (plik .salt), żeby „zapamiętaj mnie”
przetrwało nocne przebudowy.
"""
import base64
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
ITER = 600000

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Panel treningowy</title>
<style>
:root { --bg: #F3EDE3; --card: #FFFFFF; --ink: #13233F; --muted: #6B7280; --accent: #EC7FA9; --line: #E2D9CA; }
@media (prefers-color-scheme: dark) { :root { --bg: #0F1726; --card: #17213A; --ink: #F3EDE3; --muted: #9AA3B5; --line: #26314D; } }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--ink);
       font: 16px/1.5 -apple-system, system-ui, sans-serif; padding: 16px; }
form { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 32px 28px; width: 100%; max-width: 360px; }
h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -0.01em; }
p { margin: 0 0 20px; color: var(--muted); font-size: 14px; }
input[type=password] { width: 100%; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--line);
       background: transparent; color: var(--ink); font-size: 16px; }
label { display: flex; gap: 8px; align-items: center; margin: 14px 0 20px; font-size: 14px; color: var(--muted); }
button { width: 100%; padding: 12px; border: 0; border-radius: 10px; background: var(--accent); color: #13233F;
         font-weight: 600; font-size: 16px; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; }
#err { color: #C0392B; font-size: 14px; min-height: 20px; margin: 10px 0 0; }
</style>
</head>
<body>
<form id="f">
  <h1>dziubek cycling</h1>
  <p>Panel treningowy</p>
  <input id="pw" type="password" placeholder="Hasło" autocomplete="current-password" autofocus>
  <label><input id="rem" type="checkbox" checked> Zapamiętaj na 30 dni</label>
  <button id="btn">Wejdź</button>
  <div id="err"></div>
</form>
<script>
{
const P = __PAYLOAD__;
const KEY = 'panel-key-' + P.salt;
const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const tob64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
async function derive(pw) {
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'PBKDF2', salt: b64(P.salt), iterations: P.iter, hash: 'SHA-256' },
    base, { name: 'AES-GCM', length: 256 }, true, ['decrypt']);
}
async function show(key) {
  if (document.readyState !== 'complete') await new Promise(r => addEventListener('load', r, { once: true }));
  const html = new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64(P.iv) }, key, b64(P.ct)));
  document.open(); document.write(html); document.close();
}
(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved && saved.exp > Date.now()) {
      const key = await crypto.subtle.importKey('raw', b64(saved.k), 'AES-GCM', false, ['decrypt']);
      await show(key);
    }
  } catch (e) { try { localStorage.removeItem(KEY); } catch (_) {} }
})();
document.getElementById('f').addEventListener('submit', async ev => {
  ev.preventDefault();
  const btn = document.getElementById('btn'), err = document.getElementById('err');
  btn.disabled = true; err.textContent = '';
  try {
    const key = await derive(document.getElementById('pw').value);
    if (document.getElementById('rem').checked) {
      try {
        const raw = await crypto.subtle.exportKey('raw', key);
        localStorage.setItem(KEY, JSON.stringify({ k: tob64(raw), exp: Date.now() + 30 * 864e5 }));
      } catch (_) {}
    }
    await show(key);
  } catch (e) {
    try { localStorage.removeItem(KEY); } catch (_) {}
    err.textContent = 'Złe hasło';
    btn.disabled = false;
  }
});
}
</script>
</body>
</html>
"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    pw = os.environ.get("DASHBOARD_PASSWORD")
    if not pw:
        sys.exit("Brak DASHBOARD_PASSWORD")
    salt = open(os.path.join(HERE, ".salt")).read().strip()
    key = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER, 32)
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, open(src, "rb").read(), None)
    payload = {"salt": base64.b64encode(bytes.fromhex(salt)).decode(), "iv": base64.b64encode(iv).decode(),
               "ct": base64.b64encode(ct).decode(), "iter": ITER}
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, "w", encoding="utf-8").write(PAGE.replace("__PAYLOAD__", json.dumps(payload)))
    print("Zaszyfrowano: " + dst)


if __name__ == "__main__":
    main()
