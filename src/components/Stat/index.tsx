import { intComma } from '@/utils/utils';
import styles from './style.module.css';

type StatTone =
  | 'year'
  | 'runs'
  | 'distance'
  | 'pace'
  | 'streak'
  | 'heart'
  | 'place'
  | 'period';

interface IStatProperties {
  value: string | number;
  description: string;
  className?: string;
  citySize?: 3 | 4 | 5 | 6;
  onClick?: () => void;
  valueTone?: StatTone;
  descriptionTone?: StatTone;
}

const textSizeClass = {
  3: 'text-3xl',
  4: 'text-4xl',
  5: 'text-5xl',
  6: 'text-6xl',
};

const toneClass = {
  year: styles.toneYear,
  runs: styles.toneRuns,
  distance: styles.toneDistance,
  pace: styles.tonePace,
  streak: styles.toneStreak,
  heart: styles.toneHeart,
  place: styles.tonePlace,
  period: styles.tonePeriod,
};

const toneForDescription = (description: string): StatTone => {
  if (/heart/i.test(description)) return 'heart';
  if (/pace/i.test(description)) return 'pace';
  if (/streak/i.test(description)) return 'streak';
  if (/\bKM\b/i.test(description)) return 'distance';
  if (/runs/i.test(description)) return 'runs';
  if (/country|province|city|国家|省份|城市/i.test(description)) return 'place';
  if (/year|journey|年里/i.test(description)) return 'year';
  return 'period';
};

const Stat = ({
  value,
  description,
  className = 'pb-2 w-full',
  citySize,
  onClick,
  valueTone,
  descriptionTone,
}: IStatProperties) => {
  const inferredTone = toneForDescription(description);

  return (
    <div className={`${styles.stat} ${className}`} onClick={onClick}>
      <span
        className={`${styles.value} ${toneClass[valueTone || inferredTone]} ${
          textSizeClass[citySize || 5]
        } font-bold italic`}
      >
        {intComma(value.toString())}
      </span>
      <span
        className={`${styles.description} ${
          toneClass[descriptionTone || inferredTone]
        } text-lg font-semibold italic`}
      >
        {description}
      </span>
    </div>
  );
};

export default Stat;
