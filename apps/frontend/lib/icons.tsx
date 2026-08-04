import type { SVGProps } from "react";

/**
 * Hand-rolled lucide-style stroke icon set — the ONLY icon system in this
 * app. Do not add lucide-react or any second icon system; every icon must
 * come from this file. Path data follows the lucide.dev stroke convention
 * (24x24 viewBox, round caps/joins, strokeWidth 2).
 */
function Icon({
  children,
  ...props
}: SVGProps<SVGSVGElement> & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={props.width ?? 20}
      height={props.height ?? 20}
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconSend = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M3.71 3.29a1 1 0 0 0-1.36 1.24l3.2 6.4a1 1 0 0 1 0 .94l-3.2 6.4a1 1 0 0 0 1.36 1.24l17.5-8.75a1 1 0 0 0 0-1.79Z" />
    <path d="M6.75 12h13.5" />
  </Icon>
);

export const IconPaperclip = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M13.5 6.5 7.62 12.38a3.5 3.5 0 1 0 4.95 4.95l7.07-7.07a5.5 5.5 0 1 0-7.78-7.78L4.5 9.85a7.5 7.5 0 0 0 10.6 10.6" />
  </Icon>
);

export const IconPlus = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);

export const IconChevronRight = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m9 18 6-6-6-6" />
  </Icon>
);

export const IconSun = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </Icon>
);

export const IconMoon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a7 7 0 1 0 10.5 10.5Z" />
  </Icon>
);

export const IconLogOut = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </Icon>
);

export const IconUser = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M20 21a8 8 0 0 0-16 0" />
    <circle cx="12" cy="7" r="4" />
  </Icon>
);

export const IconCheckCircle = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M21.8 10A10 10 0 1 1 17 3.34" />
    <path d="m9 11 3 3L22 4" />
  </Icon>
);

export const IconUsers = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
  </Icon>
);

export const IconAlertTriangle = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
    <path d="M12 9v4M12 17h.01" />
  </Icon>
);

export const IconShieldAlert = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    <path d="M12 8v4M12 16h.01" />
  </Icon>
);

export const IconOctagonAlert = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86Z" />
    <path d="M12 8v4M12 16h.01" />
  </Icon>
);

export const IconClock = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 6v6l4 2" />
  </Icon>
);

export const IconDollarSign = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 1v22" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
  </Icon>
);

export const IconWrench = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M14.7 6.3a4 4 0 0 0-5.6 5.6L3 18l3 3 6.1-6.1a4 4 0 0 0 5.6-5.6l-2.5 2.5-2-2Z" />
  </Icon>
);

export const IconAlertCircle = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4M12 16h.01" />
  </Icon>
);

export const IconCheck = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M20 6 9 17l-5-5" />
  </Icon>
);

export const IconBuilding = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M6 22V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v18" />
    <path d="M2 22h20" />
    <path d="M9 8h1M14 8h1M9 12h1M14 12h1M9 16h1M14 16h1" />
  </Icon>
);

export const IconDownload = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 3v13" />
    <path d="m7 11 5 5 5-5" />
    <path d="M4 21h16" />
  </Icon>
);

export const IconMic = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 11a7 7 0 0 1-14 0M12 18v4M8 22h8" />
  </Icon>
);

export const IconCopy = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </Icon>
);

export const IconEdit = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    <path d="m15 5 4 4" />
  </Icon>
);

export const IconX = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icon>
);

export const IconSettings = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
  </Icon>
);

export const IconTrash = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M3 6h18" />
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6M14 11v6" />
  </Icon>
);

export const IconMonitor = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="2" y="3" width="20" height="14" rx="2" />
    <path d="M8 21h8M12 17v4" />
  </Icon>
);

// Task-category icon set
export const IconBolt = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M13 2 3 14h9l-1 8 10-12h-9Z" />
  </Icon>
);

export const IconDroplet = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M12 2s7 8.5 7 13a7 7 0 0 1-14 0c0-4.5 7-13 7-13Z" />
  </Icon>
);

export const IconGrid = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </Icon>
);

export const IconHammer = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m15 12-8.5 8.5a1.5 1.5 0 0 1-2-2L13 10" />
    <path d="M17.5 3.5 21 7l-3 3-5-5 3-3Z" />
    <path d="m13 10 4-4" />
  </Icon>
);

export const IconBrush = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M9.06 11.9 3 21l6-2.5 3.5-3.5" />
    <path d="M12.5 14 21 5.5a2.12 2.12 0 0 0-3-3L9.5 11" />
  </Icon>
);

export const IconWind = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M3 8h9.5a2.5 2.5 0 1 0-2.34-3.5" />
    <path d="M3 12h13.5a2.5 2.5 0 1 1-2.34 3.5" />
    <path d="M3 16h7.5a2.5 2.5 0 1 1-2.34 3.5" />
  </Icon>
);

export const IconStar = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M11.53 2.53a.5.5 0 0 1 .94 0l2.4 6.1a.5.5 0 0 0 .44.32l6.55.35a.5.5 0 0 1 .29.89l-5.11 4.14a.5.5 0 0 0-.17.53l1.72 6.33a.5.5 0 0 1-.75.55l-5.55-3.57a.5.5 0 0 0-.54 0l-5.55 3.57a.5.5 0 0 1-.75-.55l1.72-6.33a.5.5 0 0 0-.17-.53L1.85 10.2a.5.5 0 0 1 .3-.9l6.54-.34a.5.5 0 0 0 .44-.32Z" />
  </Icon>
);

// Mobile sidebar toggle — the app has no icon for this because the sidebar
// was always visible until the responsive pass added a collapsible drawer
// below the `lg` breakpoint.
export const IconMenu = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Icon>
);
