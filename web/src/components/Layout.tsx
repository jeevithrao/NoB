import { Outlet } from 'react-router-dom';
import { NavBar } from './NavBar';

export function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t-2 border-kaapi/10 py-6 text-center font-mono text-[11px] text-kaapi/40 tracking-wide">
        NEIGHBOURHOODS OF BANGALORE \u00b7 WALK SLOWLY
      </footer>
    </div>
  );
}
