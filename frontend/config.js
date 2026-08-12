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
window.API_BASE = "";
