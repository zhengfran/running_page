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
  3: 'text-lg',
  4: 'text-xl',
  5: 'text-3xl',
  6: 'text-4xl',
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
  const resolvedValueTone = valueTone || inferredTone;
  const resolvedDescriptionTone = descriptionTone || inferredTone;

  return (
    <div className={`${styles.stat} ${className}`} onClick={onClick}>
      <span
        className={`${styles.value} ${resolvedValueTone ? toneClass[resolvedValueTone] : ''} ${textSizeClass[citySize || 5]} font-medium`}
      >
        {intComma(value.toString())}
      </span>
      <span
        className={`${styles.description} ${resolvedDescriptionTone ? toneClass[resolvedDescriptionTone] : ''} text-sm font-normal`}
      >
        {description}
      </span>
    </div>
  );
};

export default Stat;
