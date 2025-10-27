/**
 * React 19 Compatibility Shim
 * 
 * Ensures React hooks are available globally for libraries that expect them
 * Fixes: "Cannot read properties of undefined (reading 'useLayoutEffect')"
 */

import * as React from 'react';

// Make React available globally for legacy libraries
if (typeof window !== 'undefined') {
  (window as any).React = React;
}

export default React;
