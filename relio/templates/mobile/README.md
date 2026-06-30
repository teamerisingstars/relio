# relio-mobile

A thin React Native / Expo client for a Relio backend, talking to it over the
generated TypeScript SDK (`src/sdk/`).

## Run
```
npm install
npm start            # then press i (iOS) or a (Android)
```

Set the backend URL in `App.tsx` to your machine's LAN IP when running on a
physical device (a phone can't reach the host's `localhost`).

## Regenerate the SDK (after backend API changes)
```
relio sdk --out src/sdk
```

> Note: streaming chat (`client.chat`) relies on a streaming `fetch` body, which
> React Native does not support. This starter uses the memory endpoints; for
> chat, add a non-streaming endpoint or a streaming-capable transport.
