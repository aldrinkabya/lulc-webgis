# Frontend — Bangladesh LULC WebGIS

Next.js web application that provides the interactive map interface for the WebGIS platform.

## Development

```bash
npm install
npm run dev        # Starts at http://localhost:3000
```

## Configuration

Set `NEXT_PUBLIC_API_URL` in a `.env.local` file (or the root `.env`) to point at the backend API server:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Build

```bash
npm run build      # Production build
npm start          # Serve production build
```

See the [root README](../README.md) for full project documentation.
