import PropTypes from 'prop-types';
import React from 'react';
import { Helmet } from 'react-helmet-async';
import Header from '@/components/Header';
import useSiteMetadata from '@/hooks/useSiteMetadata';
import useSiteLanguage from '@/hooks/useSiteLanguage';
import styles from './style.module.css';

const Layout = ({ children }: React.PropsWithChildren) => {
  const { siteTitle, description } = useSiteMetadata();
  const language = useSiteLanguage();

  return (
    <>
      <Helmet htmlAttributes={{ lang: language === 'zh' ? 'zh-CN' : 'en' }} bodyAttributes={{ class: styles.body }}>
        <title>{language === 'zh' ? '跑步探索器 — 郑智诚' : siteTitle}</title>
        <meta
          name="description"
          content={language === 'zh' ? '郑智诚的跑步记录、路线与年度轨迹。' : description}
        />
        <meta name="keywords" content="running, running history, running map" />
      </Helmet>
      <a className={styles.skipLink} href="#running-explorer">
        {language === 'zh' ? '跳到跑步探索器' : 'Skip to running explorer'}
      </a>
      <Header />
      <main className={styles.main} id="running-explorer">
        <div className={styles.page}>{children}</div>
      </main>
    </>
  );
};

Layout.propTypes = { children: PropTypes.node.isRequired };

export default Layout;
