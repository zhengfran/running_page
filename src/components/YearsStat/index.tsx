import YearStat from '@/components/YearStat';
import useActivities from '@/hooks/useActivities';
import { INFO_MESSAGE } from '@/utils/const';
import styles from './style.module.css';

const YearsStat = ({
  year,
  onClick,
}: {
  year: string;
  onClick: (_year: string) => void;
}) => {
  const { years } = useActivities();
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
          {INFO_MESSAGE(years.length, year)}
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
