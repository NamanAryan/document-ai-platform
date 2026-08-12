/**
 * Runtime configuration for the frontend.
 *
 * Leave API_BASE empty when FastAPI serves this page itself — local
 * development, or a single Render service hosting both halves.
 *
 * When the frontend is hosted separately (e.g. Vercel) point it at the
 * backend's public URL, with no trailing slash:
 *
 *     window.API_BASE = "https://your-service.onrender.com";
 *
 * The backend must also list this page's origin in CORS_ALLOW_ORIGINS.
 */
window.API_BASE = "https://docai-platform-api-9h3i.onrender.com";

/**
 * Minutes between background pings that keep a sleeping Render free instance
 * awake while this page is open. Set to 0 to disable.
 *
 * This only covers the time someone actually has the app open — the scheduled
 * GitHub Action is what keeps the service warm the rest of the time.
 */
window.KEEPALIVE_MINUTES = 10;
