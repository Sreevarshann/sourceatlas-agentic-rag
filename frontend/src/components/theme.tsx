"use client";

import { useCallback, useSyncExternalStore } from "react";

const EV = "sa-theme";
export const themeInitScript = `(function(){try{var t=localStorage.getItem("sa-theme");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.dataset.theme=t}catch(e){}})()`;
const sub = (cb: () => void) => (window.addEventListener(EV, cb), () => window.removeEventListener(EV, cb));
const snap = () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

export function useTheme() {
  const theme = useSyncExternalStore(sub, snap, () => "light" as const);
  const toggle = useCallback(() => {
    const next = snap() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("sa-theme", next);
    } catch {}
    window.dispatchEvent(new Event(EV));
  }, []);
  return { theme, toggle };
}
