import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en';
import mr from './mr';

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'mr', label: 'मराठी' },
] as const;
export type Lang = (typeof LANGUAGES)[number]['code'];

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'en' || saved === 'mr') return saved;
  } catch {
    /* storage blocked */
  }
  return navigator.language?.startsWith('mr') ? 'mr' : 'en';
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, mr: { translation: mr } },
  lng: initialLang(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem('lang', lng);
  } catch {
    /* ignore */
  }
});
document.documentElement.lang = i18n.language;

export default i18n;
