import { createContext, useContext, useEffect, useState } from "react";

interface ThemeValue {
  dark: boolean;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeValue>({ dark: false, toggle: () => undefined });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [dark, setDark] = useState(() => localStorage.getItem("kabadi_theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("kabadi_theme", dark ? "dark" : "light");
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0e241c" : "#123d31");
  }, [dark]);

  return <ThemeContext.Provider value={{ dark, toggle: () => setDark((value) => !value) }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
