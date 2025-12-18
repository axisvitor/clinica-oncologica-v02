/**
 * Mock for next/image to prevent Next.js loading
 */

module.exports = {
  __esModule: true,
  default: function Image(props) {
    // eslint-disable-next-line jsx-a11y/alt-text
    return React.createElement('img', props)
  }
}
