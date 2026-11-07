import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { EchoText } from '../components/EchoText';

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <EchoText text="404" className="text-[clamp(5rem,20vw,12rem)]" />
      <p className="text-xl">{t('notFound.title')}</p>
      <Link to="/" className="btn-pill">
        {t('notFound.back')}
      </Link>
    </div>
  );
}
