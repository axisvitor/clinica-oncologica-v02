// Babel config for Jest only (doesn't affect Next.js build)
module.exports = {
  presets: [
    ['@babel/preset-env', { targets: { node: 'current' } }]
  ]
};
