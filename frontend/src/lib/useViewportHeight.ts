import { useEffect } from "react";
/** Keep the editing sheet above a virtual keyboard without changing trip state. */
export function useViewportHeight() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        document.documentElement.style.setProperty(
          "--app-height",
          viewport.scale === 1 ? `${viewport.height}px` : "100dvh",
        );
        if (document.activeElement instanceof HTMLInputElement)
          document.activeElement.scrollIntoView({ block: "nearest" });
      });
    };
    update();
    viewport.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      viewport.removeEventListener("resize", update);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
}
