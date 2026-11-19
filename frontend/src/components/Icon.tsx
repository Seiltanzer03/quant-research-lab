export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    market: 'M3 3v18h18 M7 15l4-5 4 3 5-8',
    lab: 'M9 3h6 M10 3v6L4 19q-1 2 2 2h12q3 0 2-2L14 9V3 M8 14h8',
    history: 'M3 10a9 9 0 1 1 2 8 M3 4v6h6 M12 7v5l3 2',
    data: 'M20 6c0 2-4 3-8 3S4 8 4 6s4-3 8-3 8 1 8 3Z M4 6v12c0 2 4 3 8 3s8-1 8-3V6 M4 12c0 2 4 3 8 3s8-1 8-3',
    modules: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    arrow: 'M7 17 17 7 M7 7h10v10',
    github: 'M9 19c-5 2-5-2-7-2 M15 22v-4q0-2-1-2c4 0 6-2 6-5q0-2-1-3 1-3-1-4-3 0-5 2-4-2-6-2-2 1-1 4-1 1-1 3 0 5 6 5-1 1-1 3v3',
    clock: 'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    upload: 'M12 16V3 M7 8l5-5 5 5 M4 15v5h16v-5',
    check: 'm5 12 4 4L19 6',
    info: 'M12 11v6 M12 7v1 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    chevron: 'm9 5 7 7-7 7',
    target: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0 M12 10v4 M10 12h4',
    download: 'M12 3v13 M7 11l5 5 5-5 M4 17v4h16v-4',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.info} /></svg>;
}
