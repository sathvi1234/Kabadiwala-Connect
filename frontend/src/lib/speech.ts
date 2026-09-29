export function speechLang(lang: string) {
  if (lang === "hi") return "hi-IN";
  if (lang === "mr") return "mr-IN";
  return "en-IN";
}

export function speak(text: string, lang: string) {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = speechLang(lang);
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

export function listen(lang: string): Promise<string> {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return Promise.reject(new Error("unsupported"));
  const recognition = new Recognition();
  recognition.lang = speechLang(lang);
  return new Promise((resolve, reject) => {
    recognition.onresult = (event) => resolve(event.results[0][0].transcript);
    recognition.onerror = () => reject(new Error("speech_error"));
    recognition.start();
  });
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

interface SpeechRecognitionCtor {
  new (): {
    lang: string;
    start: () => void;
    onresult: ((event: { results: { 0: { 0: { transcript: string } } } }) => void) | null;
    onerror: (() => void) | null;
  };
}
