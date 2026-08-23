"use strict";

/**
 * Guard for `npm run dist:signed`.
 *
 * electron-builder signs everything (app exe, NSIS installer + uninstaller and
 * every packaged executable) when CSC_LINK / CSC_KEY_PASSWORD are set:
 *
 *   PowerShell:
 *     $env:CSC_LINK        = "C:\certs\my-codesign.pfx"   # path or base64 pfx
 *     $env:CSC_KEY_PASSWORD= "my-password"                # optional
 *     npm run dist:signed
 */

const fs = require("node:fs");

const link = process.env.CSC_LINK;
const password = process.env.CSC_KEY_PASSWORD;

const isBase64 = /^[A-Za-z0-9+/=]+$/.test(link || "")

if (!link) {
  console.error("[dist:signed] CSC_LINK is not set.");
  console.error("  Set CSC_LINK to your code-signing certificate (.pfx / .p12, path or base64)");
  console.error("  and optionally CSC_KEY_PASSWORD for its private-key password:");
  console.error('    $env:CSC_LINK = "C:\\certs\\codesign.pfx"');
  console.error('    $env:CSC_KEY_PASSWORD = "secret"');
  console.error("  Then run:  npm run dist:signed");
  process.exit(1);
}

if (!isBase64 && !fs.existsSync(link)) {
  console.error(`[dist:signed] certificate file not found: ${link}`);
  process.exit(1);
}

console.log(
  `[dist:signed] signing with ${isBase64 ? "base64-encoded pfx" : link}` +
    (password ? "" : " (no password — key must be unprotected)")
);