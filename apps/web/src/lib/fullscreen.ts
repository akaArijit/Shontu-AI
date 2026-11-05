export type FullscreenAction = "enter" | "exit" | "toggle" | "escape";

/**
 * Small, testable state machine for the graph workspace.
 *
 * The browser Fullscreen API is still the primary path; this state also drives
 * the CSS full-screen fallback so the graph stays usable when the API is
 * unavailable (for example inside an embedded webview).
 */
export function nextFullscreenState(
  active: boolean,
  action: FullscreenAction,
): boolean {
  if (action === "enter") return true;
  if (action === "exit" || action === "escape") return false;
  return !active;
}

export const FULLSCREEN_WORKSPACE_CLASS =
  "fixed inset-0 z-[70] overflow-y-auto bg-ink-950 p-3 sm:p-4";

export function fullscreenWorkspaceClass(active: boolean): string {
  return active ? FULLSCREEN_WORKSPACE_CLASS : "";
}

/**
 * The graph fills the available viewport height in full screen instead of the
 * normal page-oriented 78vh canvas.  The minimum keeps controls and tooltips
 * usable on short laptop screens.
 */
export function graphCanvasClass(active: boolean): string {
  const size = active
    ? "h-[calc(100vh-270px)] min-h-[420px]"
    : "h-[78vh] min-h-[760px]";
  return `relative ${size} w-full overflow-hidden rounded-2xl border border-warm-500/30 bg-peach-200 shadow-canvas`;
}
