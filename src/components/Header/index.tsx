import { useEffect, useState } from 'react';
import styles from './style.module.css';

const mainSite = 'https://www.zhengzhicheng.com';

const Header = () => {
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
          Embedded engineer
          <br />
          and runner
        </p>
      </div>
      <nav className={styles.nav} aria-label="Primary navigation">
        <a href={`${mainSite}/`}>Home</a>
        <a href={`${mainSite}/projects.html`}>Projects</a>
        <a href={`${mainSite}/writing.html`}>Writing</a>
        <a href="/" aria-current="page">
          Running
        </a>
        <a href={`${mainSite}/about.html`}>About</a>
      </nav>
      <div className={styles.controls}>
        <button
          type="button"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
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
