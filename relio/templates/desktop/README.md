# relio-desktop

A Tauri desktop shell wrapping the Relio React UI (same components as the web
client) on the generated TypeScript SDK. Tauri renders the Vite frontend in a
native webview, so streaming chat works (unlike React Native).

## Run
```
npm install
npm run tauri dev      # requires the Rust toolchain (https://rustup.rs)
```

## Build a native installer
```
npm run tauri build
```

## Regenerate the SDK (after backend API changes)
```
relio sdk --out src/sdk
```

> Roadmap: bundle the Relio engine + SQLite as a Tauri sidecar for a fully
> offline, on-device app (see the framework architecture doc, §11.3).
