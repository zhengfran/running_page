import { useEffect, useState } from 'react';
import useSiteLanguage, { setSiteLanguage } from '@/hooks/useSiteLanguage';
import styles from './style.module.css';

const mainSite = 'https://www.zhengzhicheng.com';

const Header = () => {
  const language = useSiteLanguage();
  const t = (english: string, chinese: string) =>
    language === 'zh' ? chinese : english;
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      return localStorage.getItem('zz-theme') === 'dark' ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('zz-theme', theme);
    } catch {
      // Theme persistence is optional in restricted browser contexts.
    }
  }, [theme]);

  return (
    <aside className={styles.rail}>
      <div className={styles.identity}>
        <a className={styles.name} href={`${mainSite}/`}>
          Zheng<br />
          Zhicheng
        </a>
        <p>
          {t('Embedded engineer', '嵌入式工程师')}
          <br />
          {t('and runner', '与跑者')}
        </p>
      </div>
      <nav className={styles.nav} aria-label={t('Primary navigation', '主导航')}>
        <a href={`${mainSite}/`}>{t('Home', '首页')}</a>
        <a href={`${mainSite}/projects.html`}>{t('Projects', '项目')}</a>
        <a href={`${mainSite}/writing.html`}>{t('Writing', '写作')}</a>
        <a href="/" aria-current="page">
          {t('Running', '跑步')}
        </a>
        <a href={`${mainSite}/about.html`}>{t('About', '关于')}</a>
      </nav>
      <div className={styles.controls}>
        <button
          type="button"
          aria-label={language === 'zh' ? 'Switch to English' : '切换到中文'}
          onClick={() => setSiteLanguage(language === 'zh' ? 'en' : 'zh')}
        >
          {language === 'zh' ? 'EN' : '中'}
        </button>
        <button
          type="button"
          aria-label={t(
            `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`,
            `切换到${theme === 'dark' ? '浅色' : '深色'}主题`
          )}
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          ◐
        </button>
        <a href="https://github.com/zhengfran">GitHub</a>
      </div>
      <p className={styles.place}>
        Singapore
        <br />
        01°17′N
      </p>
    </aside>
  );
};

export default Header;
