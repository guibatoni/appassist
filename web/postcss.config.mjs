/** Tailwind CSS v4 must be processed by PostCSS in the production build.
 * The original v0 export shipped @apply and @theme as raw CSS, leaving
 * React/Tk WebView completely unstyled despite a successful Next.js build.
 */
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
}

export default config
