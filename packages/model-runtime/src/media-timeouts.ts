const DEFAULT_TIMEOUT_MS = 30 * 60_000;

export function mediaTimeoutMs(kind: "image" | "video"): number {
    try {
        const key = kind === "image" ? "canvas.imageRequestMinutes" : "canvas.videoPollMinutes";
        const ms = Number(window.localStorage.getItem(key)) * 60_000;
        if (Number.isFinite(ms) && ms >= 3000 && ms <= 2_147_483_647) return ms;
    } catch {
        // Storage may be unavailable or this may run outside a browser.
    }
    return DEFAULT_TIMEOUT_MS;
}
