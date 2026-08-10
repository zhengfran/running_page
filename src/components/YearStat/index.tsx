import { lazy, Suspense } from 'react';
import Stat from '@/components/Stat';
import useActivities from '@/hooks/useActivities';
import { formatPace } from '@/utils/utils';
import useHover from '@/hooks/useHover';
import { yearStats } from '@assets/index';
import { loadSvgComponent } from '@/utils/svgUtils';
import useSiteLanguage from '@/hooks/useSiteLanguage';

const YearStat = ({
  year,
  onClick,
  selected = false,
}: {
  year: string;
  onClick: (_year: string) => void;
  selected?: boolean;
}) => {
  const language = useSiteLanguage();
  const t = (english: string, chinese: string) =>
    language === 'zh' ? chinese : english;
  let { activities: runs, years } = useActivities();
  // for hover
  const [hovered, eventHandlers] = useHover();
  // lazy Component
  const YearSVG = lazy(() => loadSvgComponent(yearStats, `./year_${year}.svg`));

  if (years.includes(year)) {
    runs = runs.filter((run) => run.start_date_local.slice(0, 4) === year);
  }
  let sumDistance = 0;
  let streak = 0;
  let pace = 0; // eslint-disable-line no-unused-vars
  let paceNullCount = 0; // eslint-disable-line no-unused-vars
  let heartRate = 0;
  let heartRateNullCount = 0;
  let totalMetersAvail = 0;
  let totalSecondsAvail = 0;
  runs.forEach((run) => {
    sumDistance += run.distance || 0;
    if (run.average_speed) {
      pace += run.average_speed;
      totalMetersAvail += run.distance || 0;
      totalSecondsAvail += (run.distance || 0) / run.average_speed;
    } else {
      paceNullCount++;
    }
    if (run.average_heartrate) {
      heartRate += run.average_heartrate;
    } else {
      heartRateNullCount++;
    }
    if (run.streak) {
      streak = Math.max(streak, run.streak);
    }
  });
  sumDistance = parseFloat((sumDistance / 1000.0).toFixed(1));
  const avgPace = formatPace(totalMetersAvail / totalSecondsAvail);
  const hasHeartRate = !(heartRate === 0);
  const avgHeartRate = (heartRate / (runs.length - heartRateNullCount)).toFixed(
    0
  );
  return (
    <div
      className="cursor-pointer"
      onClick={() => onClick(year)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick(year);
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={t(`Show ${year} running data`, `显示 ${year === 'Total' ? '全部' : year} 跑步数据`)}
      aria-pressed={selected}
      {...eventHandlers}
    >
      <section>
        <Stat value={year === 'Total' ? t('Total', '全部') : year} description={t(' Journey', ' 年记录')} />
        <Stat value={runs.length} description={t(' Runs', ' 次跑步')} />
        <Stat value={sumDistance} description=" KM" />
        <Stat value={avgPace} description={t(' Avg Pace', ' 平均配速')} />
        <Stat value={`${streak} ${t('day', '天')}`} description={t(' Streak', ' 连续记录')} />
        {hasHeartRate && (
          <Stat value={avgHeartRate} description={t(' Avg Heart Rate', ' 平均心率')} />
        )}
      </section>
      {year !== 'Total' && hovered && (
        <Suspense fallback="loading...">
          <YearSVG className="my-4 h-4/6 w-4/6 border-0 p-0" />
        </Suspense>
      )}
      <hr />
    </div>
  );
};

export default YearStat;
