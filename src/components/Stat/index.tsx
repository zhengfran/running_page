import { intComma } from '@/utils/utils';

interface IStatProperties {
  value: string | number;
  description: string;
  className?: string;
  citySize?: 3 | 4 | 5 | 6;
  onClick?: () => void;
}

const textSizeClass = {
  3: 'text-3xl',
  4: 'text-4xl',
  5: 'text-5xl',
  6: 'text-6xl',
};

const Stat = ({
  value,
  description,
  className = 'pb-2 w-full',
  citySize,
  onClick,
}: IStatProperties) => (
  <div className={`${className}`} onClick={onClick}>
    <span className={`${textSizeClass[citySize || 5]} font-bold italic`}>
      {intComma(value.toString())}
    </span>
    <span className="text-lg font-semibold italic">{description}</span>
  </div>
);

export default Stat;
