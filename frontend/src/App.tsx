import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LoadingBlock } from './components/States';
import HomePage from './pages/HomePage';

// The map page loads first; the rest are split into their own chunks.
const SitePage = lazy(() => import('./pages/SitePage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const ProjectPage = lazy(() => import('./pages/ProjectPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const NotFound = lazy(() => import('./pages/NotFound'));

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-10">
          <LoadingBlock />
        </div>
      }
    >
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="site/:id" element={<SitePage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="project" element={<ProjectPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
