"""Apply fork-specific media timeouts, failing closed on upstream drift."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()

runtime = "packages/model-runtime/src/"
workbench = "packages/workbench/src/services/"
helper = '''const DEFAULT_TIMEOUT_MS = 30 * 60_000;

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
'''
changes = {
    runtime + "call-scripts/openai.ts": [("timeout: 600000,", "timeout: utils.imageRequestTimeoutMs,", 4)],
    runtime + "call-scripts/gemini.ts": [("timeout: 600000,", "timeout: utils.imageRequestTimeoutMs,", 1)],
    runtime + "script.ts": [
        ('import type { ModelCapability }', 'import { mediaTimeoutMs } from "./media-timeouts.js";\nimport type { ModelCapability }', 1),
        ('function createPoll(signal?: AbortSignal)', 'function createPoll(defaultTimeoutMs: number, signal?: AbortSignal)', 1),
        ('options?.timeoutMs ?? 300000', 'options?.timeoutMs ?? defaultTimeoutMs', 1),
        ('poll: createPoll(signal),', 'poll: createPoll(args.capability === "video" ? mediaTimeoutMs("video") : 300000, signal),', 1),
        ('sleep: (ms: number) => sleep(ms, signal),', 'imageRequestTimeoutMs: args.capability === "image" ? mediaTimeoutMs("image") : undefined,\n            sleep: (ms: number) => sleep(ms, signal),', 1),
    ],
    workbench + "image-storage.ts": [
        ('import { network }', 'import { mediaTimeoutMs } from "@infinite-canvas/model-runtime/media-timeouts";\nimport { network }', 1),
        ('const IMAGE_DOWNLOAD_TIMEOUT_MS = 10 * 60_000;\nconst IMAGE_REMOTE_LOAD_TIMEOUT_MS = 10 * 60_000;\n', '', 1),
        ('loadImageMeta(input, options, IMAGE_REMOTE_LOAD_TIMEOUT_MS)', 'loadImageMeta(input, options, mediaTimeoutMs("image"))', 1),
        ('}, IMAGE_DOWNLOAD_TIMEOUT_MS);', '}, mediaTimeoutMs("image"));', 1),
    ],
    workbench + "api/video.ts": [
        ('import { nanoid }', 'import { mediaTimeoutMs } from "@infinite-canvas/model-runtime/media-timeouts";\nimport { nanoid }', 1),
        ('    for (let attempt = 0; attempt < 120; attempt += 1) {', '    const intervalMs = 3000;\n    const attempts = Math.ceil(mediaTimeoutMs("video") / intervalMs);\n    for (let attempt = 0; attempt < attempts; attempt += 1) {', 1),
        ('if (attempt === 119) break;', 'if (attempt === attempts - 1) break;', 1),
        ('await delay(2500, options?.signal);', 'await delay(intervalMs, options?.signal);', 1),
    ],
}
helper_path = args.root / (runtime + "media-timeouts.ts")
if args.check and (not helper_path.is_file() or helper_path.read_text(encoding="utf-8") != helper):
    parser.exit(1, "Media timeout helper is absent or changed.\n")
if not args.check and helper_path.exists():
    parser.exit(1, "Upstream now has a media timeout helper; review the patch.\n")
updated = {}
for name, replacements in changes.items():
    path = args.root / name
    source = path.read_text(encoding="utf-8")
    for old, new, count in replacements:
        if args.check:
            if new and source.count(new) != count:
                parser.exit(1, f"Missing or ambiguous patched site in {name}: {new}\n")
            if not new and old in source:
                parser.exit(1, f"Old timeout still present in {name}.\n")
        else:
            if source.count(old) != count:
                parser.exit(1, f"Upstream drift in {name}: expected {count} occurrence(s) of {old}\n")
            source = source.replace(old, new)
    updated[path] = source

if not args.check:
    for path, source in updated.items():
        path.write_text(source, encoding="utf-8", newline="\n")
    helper_path.write_text(helper, encoding="utf-8", newline="\n")
print("Media timeouts verified" if args.check else "Media timeouts patched")
