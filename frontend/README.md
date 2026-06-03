# DBInspector — Frontend

UI minimalista para el backend de DBInspector. Hace una pregunta en lenguaje natural,
muestra el progreso del pipeline en tiempo real, y al terminar presenta el SQL generado,
la tabla de resultados, una gráfica y el resumen ejecutivo.

## Stack

- **Vite + React 19 + TypeScript** (HMR, build instantáneo)
- **Tailwind CSS** (utility-first, dark theme custom)
- **axios** (HTTP, pineado `1.15.1` — las versiones `1.14.1`/`0.30.4` fueron comprometidas
  por el actor norcoreano *Sapphire Sleet* en marzo 2026; ver
  [issue oficial](https://github.com/axios/axios/issues/10604))
- **graphql-ws** (subscriptions sobre WebSocket)
- **Recharts** (visualización derivada del `ChartSpec` del backend)

## Arquitectura

Mirror del backend hexagonal — separación estricta de capas:

```
src/
├── domain/        Types puros (mirror de los Pydantic + GraphQL del backend)
├── api/           Adapters: axios (HTTP), graphql-ws (subscription)
├── components/    UI primitivos reutilizables (Card, Button, DataTable, ChartRenderer)
├── features/
│   └── query/     Pantalla principal — useQueryFlow + 3 vistas
└── lib/           Helpers (env)
```

**Reglas de dependencias:** `features/` ➜ `components/` + `api/` + `domain/`. `api/` ➜
`domain/`. `components/` ➜ solo `domain/`. Nunca al revés.

## Cómo arrancarlo

```bash
cd frontend
cp .env.example .env       # ajusta VITE_API_URL / VITE_WS_URL si el backend no corre en :8000
npm install
npm run dev                # http://localhost:5173
```

El backend debe estar corriendo en `http://localhost:8000` (o el host que pongas en
`VITE_API_URL`).

## Notas de seguridad

Tras la oleada de ataques de supply chain a npm en 2026 (axios, TanStack, SAP, node-ipc,
Shai-Hulud worm):

- Todas las dependencias **sensibles** (axios, recharts, graphql-ws, postcss, tailwind,
  autoprefixer) están **pineadas con versión exacta**, sin `^` ni `~`. Esto previene que
  un `npm install` futuro tire de una versión recién publicada que podría estar
  comprometida (exactamente cómo se propagó el ataque a axios).
- React/TypeScript/Vite/ESLint mantienen `^` porque son ecosistemas con cadenas de
  release más auditadas y el balance riesgo/beneficio favorece auto-updates de parches.
- Antes de cualquier `npm install` nuevo, conviene correr:
  ```bash
  npm audit
  ```

## Scripts

| Comando         | Acción                                         |
| --------------- | ---------------------------------------------- |
| `npm run dev`   | Servidor de desarrollo con HMR                 |
| `npm run build` | `tsc --noEmit` + `vite build` → `dist/`        |
| `npm run preview` | Sirve el `dist/` para humo final            |
| `npm run lint`  | Type-check (alias de `tsc --noEmit`)           |
