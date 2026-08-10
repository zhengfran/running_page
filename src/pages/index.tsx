import { useEffect, useRef, useState } from 'react';
import { Analytics } from '@vercel/analytics/react';
import Layout from '@/components/Layout';
import LocationStat from '@/components/LocationStat';
import RunMap from '@/components/RunMap';
import RunTable from '@/components/RunTable';
import SVGStat from '@/components/SVGStat';
import YearsStat from '@/components/YearsStat';
import useActivities from '@/hooks/useActivities';
import useSiteMetadata from '@/hooks/useSiteMetadata';
import useSiteLanguage from '@/hooks/useSiteLanguage';
import styles from './style.module.css';
import { IS_CHINESE } from '@/utils/const';
import {
  Activity,
  IViewState,
  filterAndSortRuns,
  filterCityRuns,
  filterTitleRuns,
  filterYearRuns,
  geoJsonForRuns,
  getBoundsForGeoData,
  scrollToMap,
  sortDateFunc,
  titleForShow,
  RunIds,
} from '@/utils/utils';

const Index = () => {
  const { siteTitle } = useSiteMetadata();
  const language = useSiteLanguage();
  const t = (english: string, chinese: string) =>
    language === 'zh' ? chinese : english;
  const { activities, thisYear, years } = useActivities();
  const yearRange = `${years.at(-1)}—${years[0]}`;
  const [year, setYear] = useState(thisYear);
  const [runIndex, setRunIndex] = useState(-1);
  const [runs, setActivity] = useState(
    filterAndSortRuns(activities, year, filterYearRuns, sortDateFunc)
  );
  const [title, setTitle] = useState('');
  const [geoData, setGeoData] = useState(geoJsonForRuns(runs));
  // for auto zoom
  const bounds = getBoundsForGeoData(geoData);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const [viewState, setViewState] = useState<IViewState>({
    ...bounds,
  });

  const clearAnimation = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = undefined;
    }
  };

  const changeByItem = (
    item: string,
    name: string,
    func: (_run: Activity, _value: string) => boolean
  ) => {
    scrollToMap();
    if (name != 'Year') {
      setYear(thisYear);
    }
    setActivity(filterAndSortRuns(activities, item, func, sortDateFunc));
    setRunIndex(-1);
    const category = language === 'zh'
      ? ({ Year: '年份', City: '城市', Title: '时段' } as Record<string, string>)[name] || name
      : name;
    setTitle(language === 'zh' ? `${item} · ${category}跑步轨迹` : `${item} ${category} Running Heatmap`);
  };

  const changeYear = (y: string) => {
    // default year
    setYear(y);

    if ((viewState.zoom ?? 0) > 3 && bounds) {
      setViewState({
        ...bounds,
      });
    }

    changeByItem(y, 'Year', filterYearRuns);
    clearAnimation();
  };

  const changeCity = (city: string) => {
    changeByItem(city, 'City', filterCityRuns);
  };

  const changeTitle = (title: string) => {
    changeByItem(title, 'Title', filterTitleRuns);
  };

  const locateActivity = (runIds: RunIds) => {
    const ids = new Set(runIds);

    const selectedRuns = !runIds.length
      ? runs
      : runs.filter((r: any) => ids.has(r.run_id));

    if (!selectedRuns.length) {
      return;
    }

    const lastRun = selectedRuns.sort(sortDateFunc)[0];

    if (!lastRun) {
      return;
    }
    setGeoData(geoJsonForRuns(selectedRuns));
    setTitle(titleForShow(lastRun));
    clearAnimation();
    scrollToMap();
  };

  useEffect(() => {
    setViewState({
      ...bounds,
    });
  }, [geoData]);

  useEffect(() => {
    const runsNum = runs.length;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      clearAnimation();
      setGeoData(geoJsonForRuns(runs));
      return clearAnimation;
    }
    // maybe change 20 ?
    const sliceNume = runsNum >= 20 ? runsNum / 20 : 1;
    let i = sliceNume;
    clearAnimation();
    const id = setInterval(() => {
      if (i >= runsNum) {
        clearAnimation();
      }

      const tempRuns = runs.slice(0, i);
      setGeoData(geoJsonForRuns(tempRuns));
      i += sliceNume;
    }, 100);
    intervalRef.current = id;

    return clearAnimation;
  }, [runs]);

  useEffect(() => {
    if (year !== 'Total') {
      return;
    }

    let svgStat = document.getElementById('svgStat');
    if (!svgStat) {
      return;
    }

    const handleClick = (e: Event) => {
      const target = e.target as HTMLElement;
      if (target.tagName.toLowerCase() === 'path') {
        // Use querySelector to get the <desc> element and the <title> element.
        const descEl = target.querySelector('desc');
        if (descEl) {
          // If the runId exists in the <desc> element, it means that a running route has been clicked.
          const runId = Number(descEl.innerHTML);
          if (!runId) {
            return;
          }
          locateActivity([runId]);
          return;
        }

        const titleEl = target.querySelector('title');
        if (titleEl) {
          // If the runDate exists in the <title> element, it means that a date square has been clicked.
          const [runDate] = titleEl.innerHTML.match(
            /\d{4}-\d{1,2}-\d{1,2}/
          ) || [`${+thisYear + 1}`];
          const runIDsOnDate = runs
            .filter((r) => r.start_date_local.slice(0, 10) === runDate)
            .map((r) => r.run_id);
          if (!runIDsOnDate.length) {
            return;
          }
          locateActivity(runIDsOnDate);
        }
      }
    };
    svgStat.addEventListener('click', handleClick);
    return () => {
      svgStat && svgStat.removeEventListener('click', handleClick);
    };
  }, [year]);

  return (
    <Layout>
      <header className={styles.intro}>
        <p>{t(`RUNNING HISTORY · ${yearRange}`, `跑步记录 · ${yearRange}`)}</p>
        <h1>{t(siteTitle, '跑步探索器')}</h1>
        <div className={styles.introCopy}>
          <p>
            {t(
              'A personal history of routes, ordinary miles, and the patterns that become visible over time.',
              '一份关于路线、普通里程，以及那些随时间逐渐显现的规律的个人记录。'
            )}
          </p>
          <span>{t('Choose a year or a row to redraw the map.', '选择年份或活动行，重新绘制地图。')}</span>
        </div>
      </header>
      <div className={styles.explorerGrid}>
        <aside className={styles.statsPanel} aria-label={t('Running filters and totals', '跑步筛选与统计')}>
        {(viewState.zoom ?? 0) <= 3 && IS_CHINESE ? (
          <LocationStat
            changeYear={changeYear}
            changeCity={changeCity}
            changeTitle={changeTitle}
          />
        ) : (
          <YearsStat year={year} onClick={changeYear} />
        )}
        </aside>
        <section
          className={styles.mapPanel}
          id="running-map-panel"
          aria-label={t('Interactive running map and activity list', '交互式跑步地图与活动列表')}
        >
          <RunMap
            title={title}
            viewState={viewState}
            geoData={geoData}
            setViewState={setViewState}
            changeYear={changeYear}
            thisYear={year}
          />
          {year === 'Total' ? (
            <SVGStat />
          ) : (
            <RunTable
              runs={runs}
              locateActivity={locateActivity}
              setActivity={setActivity}
              runIndex={runIndex}
              setRunIndex={setRunIndex}
            />
          )}
        </section>
      </div>
      <footer className={styles.footer}>
        <span>© 2026 Zheng Zhicheng</span>
        <a href="https://www.zhengzhicheng.com/">{t('Main site', '主站')}</a>
        <a href="https://github.com/zhengfran">GitHub</a>
        <a href="#running-explorer">{t('Top', '顶部')} ↑</a>
      </footer>
      {/* Enable Audiences in Vercel Analytics: https://vercel.com/docs/concepts/analytics/audiences/quickstart */}
      <Analytics />
    </Layout>
  );
};

export default Index;
