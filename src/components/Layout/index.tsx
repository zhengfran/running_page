import PropTypes from 'prop-types';
import React from 'react';
import { Helmet } from 'react-helmet-async';
import Header from '@/components/Header';
import useSiteMetadata from '@/hooks/useSiteMetadata';
import styles from './style.module.css';

const Layout = ({ children }: React.PropsWithChildren) => {
  const { siteTitle, description } = useSiteMetadata();

  return (
    <>
      <Helmet htmlAttributes={{ lang: 'en' }} bodyAttributes={{ class: styles.body }}>
        <title>{siteTitle}</title>
        <meta name="description" content={description} />
        <meta name="keywords" content="running, running archive, running map" />
      </Helmet>
      <a className={styles.skipLink} href="#running-explorer">
        Skip to running explorer
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
