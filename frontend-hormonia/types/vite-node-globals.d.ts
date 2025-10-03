declare module 'url' {
  export function fileURLToPath(url: string | URL): string
}

declare module 'path' {
  export function dirname(path: string): string
  export function resolve(...paths: string[]): string
}

