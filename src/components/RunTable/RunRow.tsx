import type React from 'react';
import {
  formatPace,
  titleForRun,
  formatRunTime,
  Activity,
  RunIds,
  RunType,
} from '@/utils/utils';
import styles from './style.module.css';
import useSiteLanguage from '@/hooks/useSiteLanguage';

interface IRunRowProperties {
  elementIndex: number;
  locateActivity: (_runIds: RunIds) => void;
  run: Activity;
  runType: RunType;
  runIndex: number;
  setRunIndex: (_ndex: number) => void;
}

const RunRow = ({
  elementIndex,
  locateActivity,
  run,
  runType,
  runIndex,
  setRunIndex,
}: IRunRowProperties) => {
  const language = useSiteLanguage();
  const distance = (run.distance / 1000.0).toFixed(2);
  const paceParts = run.average_speed ? formatPace(run.average_speed) : null;
  const heartRate = run.average_heartrate;
  const runTime = formatRunTime(run.moving_time);
  const runTitle = titleForRun(run);
  const runTypeLabel = language === 'zh'
    ? ({
        easy: '轻松跑',
        interval: '间歇',
        threshold: '阈值',
        'long run': '长距离',
        race: '比赛',
      } as Record<string, string>)[runType] || runType
    : runType;
  const handleClick = () => {
    if (runIndex === elementIndex) {
      setRunIndex(-1);
      locateActivity([]);
      return;
    }
    setRunIndex(elementIndex);
    locateActivity([run.run_id]);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleClick();
    }
  };

  return (
    <tr
      className={`${styles.runRow} ${runIndex === elementIndex ? styles.selected : ''}`}
      key={run.start_date_local}
      aria-label={language === 'zh' ? `在地图上显示 ${runTitle}` : `Show ${runTitle} on map`}
      aria-pressed={runIndex === elementIndex}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      <td>{runTitle}</td>
      <td>
        <span className={styles.runType} data-run-type={runType}>
          {runTypeLabel}
        </span>
      </td>
      <td className={styles.runDistance}>{distance}</td>
      <td>{paceParts || '—'}</td>
      <td className={styles.runHeartRate}>
        {heartRate && heartRate.toFixed(0)}
      </td>
      <td>{runTime}</td>
      <td className={styles.runDate}>{run.start_date_local}</td>
    </tr>
  );
};

export default RunRow;
