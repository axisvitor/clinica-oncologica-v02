import { describe, expect, it } from 'vitest';

import {
  getConfigValue,
  getRuntimeConfig,
  getRuntimeConfigSync,
  refreshRuntimeConfig,
} from '../../src/lib/runtime-config';
import { initializeConfiguration } from '../../src/lib/config-initializer';

describe('Configuration Initialization - Integration', () => {
  it('loads runtime config with required API and WS values', async () => {
    const config = await getRuntimeConfig();

    expect(config.VITE_API_URL).toBeTruthy();
    expect(config.VITE_WS_URL).toBeTruthy();
  });

  it('keeps runtime config stable across refresh and sync access', async () => {
    const asyncConfig = await getRuntimeConfig();
    const refreshedConfig = await refreshRuntimeConfig();
    const syncConfig = getRuntimeConfigSync();

    expect(refreshedConfig.VITE_API_URL).toBe(asyncConfig.VITE_API_URL);
    expect(syncConfig.VITE_API_URL).toBe(asyncConfig.VITE_API_URL);
    expect(syncConfig.VITE_WS_URL).toBe(asyncConfig.VITE_WS_URL);
  });

  it('initializes configuration and resolves specific keys with fallback', async () => {
    const config = await initializeConfiguration();
    const apiUrl = await getConfigValue('VITE_API_URL');
    const fallback = await getConfigValue('VITE_ANALYTICS_TRACKING_ID', 'none');

    expect(config.VITE_API_URL).toBe(apiUrl);
    expect(fallback).toBeTruthy();
  });
});
