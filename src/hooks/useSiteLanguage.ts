import { useEffect, useState } from 'react';

export type SiteLanguage = 'en' | 'zh';

const LANGUAGE_EVENT = 'zz-language-change';

const storedLanguage = (): SiteLanguage => {
  try {
    return localStorage.getItem('zz-lang') === 'zh' ? 'zh' : 'en';
  } catch {
    return 'en';
  }
};

const applyLanguage = (language: SiteLanguage) => {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  document.documentElement.dataset.lang = language;
};

export const setSiteLanguage = (language: SiteLanguage) => {
  applyLanguage(language);
  try {
    localStorage.setItem('zz-lang', language);
  } catch {
    // Language persistence is optional in restricted browser contexts.
  }
  window.dispatchEvent(new CustomEvent<SiteLanguage>(LANGUAGE_EVENT, { detail: language }));
};

const useSiteLanguage = () => {
  const [language, setLanguage] = useState<SiteLanguage>(storedLanguage);
  useEffect(() => {
    applyLanguage(language);
    const update = (event: Event) => setLanguage((event as CustomEvent<SiteLanguage>).detail);
    window.addEventListener(LANGUAGE_EVENT, update);
    return () => window.removeEventListener(LANGUAGE_EVENT, update);
  }, []);
  return language;
};

export default useSiteLanguage;
