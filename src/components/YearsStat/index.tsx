import YearStat from '@/components/YearStat';
import useActivities from '@/hooks/useActivities';
import useSiteLanguage from '@/hooks/useSiteLanguage';
import styles from './style.module.css';

const YearsStat = ({
  year,
  onClick,
}: {
  year: string;
  onClick: (_year: string) => void;
}) => {
  const { years } = useActivities();
  const language = useSiteLanguage();
  // make sure the year click on front
  const yearsArrayUpdate = [
    year,
    ...years.filter((x) => x !== year),
    ...(year === 'Total' ? [] : ['Total']),
  ];

  // for short solution need to refactor
  return (
    <div className={styles.wrapper}>
      <section className={styles.intro}>
        <p className="leading-relaxed">
          {language === 'zh'
            ? `这份跑步记录跨越 ${years.length} 年，当前显示${year === 'Total' ? '全部年份' : ` ${year} 年`}。`
            : `This running history spans ${years.length} years; the current view shows ${year === 'Total' ? 'all years' : year}.`}
          <br />
        </p>
      </section>
      <hr />
      <div className={styles.years}>
        {yearsArrayUpdate.map((itemYear) => (
          <YearStat
            key={itemYear}
            year={itemYear}
            onClick={onClick}
            selected={itemYear === year}
          />
        ))}
      </div>
    </div>
  );
};

export default YearsStat;
