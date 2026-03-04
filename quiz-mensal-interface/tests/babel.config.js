// Babel config for Jest ONLY - isolated in tests/ folder to avoid affecting Next.js
module.exports = {
  presets: [['@babel/preset-env', { targets: { node: 'current' } }]],
}
