import type { SVGProps } from 'react';

export default function IconClasses(props: SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 21V8l9-5 9 5v13" />
      <path d="M9 21V12h6v9" />
      <path d="M3 8h18" />
    </svg>
  );
}
