# ADR 0002: ATÉ frontend foundation

Status: adopted; incorporates the user's request for modern cybersecurity-focused
UI/UX with shadcn components where applicable.

Use React, TypeScript, Vite, Tailwind CSS v4, shadcn/ui components, Lucide icons,
and TanStack Query. shadcn's CLI generated the checked-in Button, Badge, Card,
and Separator components. Use the repository's `cn` utility and CSS theme tokens
to maintain them locally. TanStack Query owns health request caching, polling,
abort signals, and refresh state; the backend remains authoritative.

The visual language uses a dark neutral surface, restrained mint accents,
legible typography, clear hierarchy, and text alongside status colors. Include
keyboard focus states, a skip link, live status announcements, reduced-motion
support, and a responsive single-column mobile layout. Browser checks cover
healthy, degraded, malformed, and unreachable responses, overflow, and automated
WCAG accessibility checks. Automated checks complement future manual UX review.

Phase 0 is a single system-overview page. Do not add a router, case workflows,
dummy case metrics, or clickable navigation to nonexistent features. Select a
router when Phase 2 introduces routes. The future investigation workspace is
described as upcoming, without pretending it exists.

Pydantic OpenAPI generates the frontend's response types with openapi-typescript;
CI checks for contract drift. No browser environment contains provider secrets.
The browser calls same-origin API routes through Nginx (production container)
or the Vite proxy (development).

Sources: [shadcn/ui Vite setup](https://ui.shadcn.com/docs/installation/vite),
[Tailwind Vite plugin](https://tailwindcss.com/docs/installation/using-vite).
