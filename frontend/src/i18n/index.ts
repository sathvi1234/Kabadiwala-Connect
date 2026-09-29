import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import hi from "./hi.json";
import mr from "./mr.json";

const stored = localStorage.getItem("kabadi_lang") || "en";

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, mr: { translation: mr } },
  lng: stored,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
