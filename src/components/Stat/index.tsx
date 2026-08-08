import { intComma } from '@/utils/utils';
import styles from './style.module.css';

type StatTone = 'distance' | 'heart';

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
  distance: styles.toneDistance,
  heart: styles.toneHeart,
};

const toneForDescription = (description: string): StatTone | undefined => {
  if (/heart/i.test(description)) return 'heart';
  if (/\bKM\b/i.test(description)) return 'distance';
  return undefined;
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
        className={`${styles.value} ${
          valueTone || inferredTone ? toneClass[valueTone || inferredTone] : ''
        } ${textSizeClass[citySize || 5]} font-bold italic`}
      >
        {intComma(value.toString())}
      </span>
      <span
        className={`${styles.description} ${
          descriptionTone || inferredTone
            ? toneClass[descriptionTone || inferredTone]
            : ''
        } text-lg font-semibold italic`}
      >
        {description}
      </span>
    </div>
  );
};

export default Stat;
